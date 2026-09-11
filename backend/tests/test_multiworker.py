"""多 worker / 多副本部署适配测试:
① 定时任务分布式锁(防重复执行)
② WebSocket 跨进程广播(Redis Pub/Sub)与降级
"""
from datetime import datetime, timedelta

from app.models import Orders
from app.tasks import scheduler as sched
from app.websocket.manager import WS_CHANNEL, WebSocketManager, _match


# ===== ① 定时任务分布式锁 =====

async def test_task_skipped_when_lock_held(monkeypatch):
    """其他 worker 持有锁时:任务跳过,不执行"""
    from app.core import redis as redis_mod

    ran = []
    async def fake_setnx(key, lock_id, ttl):
        assert key == "lock:task:timeout_order_cancel"
        return False  # 锁被其他 worker 持有
    async def fake_body():
        ran.append(1)

    monkeypatch.setattr(redis_mod, "redis_setnx", fake_setnx)
    await sched._run_with_lock("timeout_order_cancel", 55, fake_body)
    assert ran == []  # 未执行


async def test_task_runs_and_releases_lock(monkeypatch):
    """抢到锁:执行任务并释放锁"""
    from app.core import redis as redis_mod

    ran, released = [], []
    async def fake_setnx(key, lock_id, ttl):
        return True
    async def fake_release(key, lock_id):
        released.append(key)
    async def fake_body():
        ran.append(1)

    monkeypatch.setattr(redis_mod, "redis_setnx", fake_setnx)
    monkeypatch.setattr(redis_mod, "redis_release_lock", fake_release)
    await sched._run_with_lock("timeout_order_cancel", 55, fake_body)
    assert ran == [1]
    assert released == ["lock:task:timeout_order_cancel"]


async def test_task_degrades_when_redis_down(monkeypatch):
    """Redis 不可用:降级为本进程执行(不阻塞业务)"""
    from app.core import redis as redis_mod

    ran = []
    async def fake_setnx(key, lock_id, ttl):
        raise ConnectionError("redis down")
    async def fake_body():
        ran.append(1)

    monkeypatch.setattr(redis_mod, "redis_setnx", fake_setnx)
    await sched._run_with_lock("timeout_order_cancel", 55, fake_body)
    assert ran == [1]  # 降级仍执行


async def test_timeout_order_task_cancels_expired(db, monkeypatch):
    """超时订单任务在锁保护下正常取消订单(业务回归)"""
    from app.core import redis as redis_mod

    async def fake_setnx(key, lock_id, ttl):
        return True
    monkeypatch.setattr(redis_mod, "redis_setnx", fake_setnx)

    # 造一个 20 分钟前的待付款订单
    o = Orders(user_id=1, address_book_id=1, number="T1",
               order_time=datetime.now() - timedelta(minutes=20),
               amount=10, pay_method=1, pay_status=0, status=1, delivery_status=1)
    db.add(o)
    await db.commit()

    # 直接调用内部实现(用测试 db 会话,避免另开连接)
    from sqlalchemy import select
    async def fake_session():
        return db
    monkeypatch.setattr(sched, "AsyncSessionLocal", lambda: _Ctx(db))

    await sched._do_deal_with_timeout_order()
    row = (await db.execute(select(Orders).where(Orders.number == "T1"))).scalar_one()
    assert row.status == 6
    assert row.cancel_reason == "支付超时，取消订单"


class _Ctx:
    """把已有 session 包成 async context manager,供任务内部使用"""
    def __init__(self, db):
        self.db = db

    async def __aenter__(self):
        return self.db

    async def __aexit__(self, *args):
        return False


# ===== ② WebSocket 跨进程广播 =====

def test_sid_match_rules():
    """连接匹配规则:admin/user 分流 + 按 userId 定向"""
    assert _match("admin-console", "admin", None) is True
    assert _match("user-1-123", "admin", None) is False
    assert _match("user-1-123", "user", None) is True
    assert _match("admin-console", "user", None) is False
    # 定向:只匹配同一 userId
    assert _match("user-1-123", "user", 1) is True
    assert _match("user-2-456", "user", 1) is False
    # 广播:target=all 匹配全部
    assert _match("user-2-456", "all", None) is True
    assert _match("admin-x", "all", None) is True


async def test_publish_to_channel(monkeypatch):
    """推送走 Redis 频道(跨 worker)"""
    from app.core import redis as redis_mod

    published = []
    async def fake_publish(channel, message):
        published.append((channel, message))
        return 1

    monkeypatch.setattr(redis_mod, "redis_publish", fake_publish)
    m = WebSocketManager()
    await m.send_to_all('{"type":1}', target="user", user_id=7)
    assert len(published) == 1
    assert published[0][0] == WS_CHANNEL
    assert '"user_id": 7' in published[0][1]


async def test_publish_fallback_when_redis_down(monkeypatch):
    """Redis 不可用:降级为仅推本进程连接"""
    from app.core import redis as redis_mod

    async def fake_publish(channel, message):
        raise ConnectionError("redis down")

    monkeypatch.setattr(redis_mod, "redis_publish", fake_publish)

    sent = []
    class _FakeWS:
        async def send_text(self, msg):
            sent.append(msg)

    m = WebSocketManager()
    m.connect("admin-console", _FakeWS())
    await m.send_to_all('{"type":1}', target="admin")
    assert sent == ['{"type":1}']  # 降级后本地推送仍可用


async def test_local_dispatch_by_user(monkeypatch):
    """订阅分发:按 target/user_id 精准推给本进程连接"""
    sent = []
    class _FakeWS:
        def __init__(self, name):
            self.name = name
        async def send_text(self, msg):
            sent.append((self.name, msg))

    m = WebSocketManager()
    m.connect("user-1-a", _FakeWS("u1"))
    m.connect("user-2-b", _FakeWS("u2"))
    m.connect("admin-console", _FakeWS("admin"))

    await m.send_local("msg-user1", target="user", user_id=1)
    assert sent == [("u1", "msg-user1")]

    sent.clear()
    await m.send_local("msg-admin", target="admin")
    assert sent == [("admin", "msg-admin")]
