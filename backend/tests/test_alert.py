"""日志告警单元测试:配置开关 / 指纹去重 / 限流 / 签名 / 失败不抛异常。

重点验证的是「告警不能拖垮业务」这条铁律 —— 发送失败、节流、意外异常
都必须在 handler 内部被吞掉,绝不能冒泡到调用方。
"""
import asyncio
import logging

from app.core import alert
from app.core.alert import FeishuAlertHandler

WEBHOOK = "https://open.feishu.cn/open-apis/bot/v2/hook/fake-for-test"


class _CapturingHandler(FeishuAlertHandler):
    """把要发送的文本捕获下来,不发真实网络请求"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.sent: list = []

    def _send_sync(self, text):
        self.sent.append(text)

    async def _send_async(self, text):
        self.sent.append(text)


def _record(msg="boom", module="app.services.demo", lineno=42, exc_info=None):
    rec = logging.LogRecord(name="uvicorn.error", level=logging.ERROR, pathname=__file__,
                            lineno=lineno, msg=msg, args=(), exc_info=exc_info)
    rec.module = module  # 默认由 pathname 推导,测试里直接指定便于构造指纹
    return rec


# ===== 配置开关 =====


def test_setup_skips_when_not_configured(monkeypatch):
    """未配置 webhook → 静默跳过,不挂载任何 handler(代码可以先合后配)"""
    monkeypatch.setattr("app.core.config.ALERT_WEBHOOK_URL", "")
    assert alert.setup_alert() is None


def test_setup_is_idempotent(monkeypatch):
    """重复调用不叠加 handler(否则同一错误会被推送多次)"""
    monkeypatch.setattr("app.core.config.ALERT_WEBHOOK_URL", WEBHOOK)
    target = logging.getLogger("uvicorn.error")
    before = len(target.handlers)

    first = alert.setup_alert()
    assert first is not None
    assert alert.setup_alert() is None  # 第二次幂等
    assert len(target.handlers) == before + 1

    target.removeHandler(first)  # 清理,避免污染其他测试


def test_handler_level_is_error():
    """只接管 ERROR 及以上 —— WARNING 多为 4xx 参数错误,推了会把真告警淹没"""
    assert FeishuAlertHandler(WEBHOOK).level == logging.ERROR


# ===== 去重 =====


def test_same_fingerprint_deduped():
    """同一处代码的同类错误,静默期内只推一次"""
    h = _CapturingHandler(WEBHOOK)
    rec = _record()
    for _ in range(5):
        h.emit(rec)
    assert len(h.sent) == 1


def test_fingerprint_ignores_message():
    """指纹必须忽略消息正文 —— 正文里带 rid/IP/耗时,每次都不同,否则去重完全失效"""
    h = _CapturingHandler(WEBHOOK)
    h.emit(_record(msg="请求异常 POST /admin/dish rid=aaaa 12.4ms"))
    h.emit(_record(msg="请求异常 POST /admin/dish rid=bbbb 11.9ms"))
    assert len(h.sent) == 1, "指纹把消息算进去了,去重失效"


def test_different_location_not_deduped():
    """不同位置的错误互不影响"""
    h = _CapturingHandler(WEBHOOK)
    h.emit(_record(lineno=1))
    h.emit(_record(lineno=2))
    h.emit(_record(module="app.other", lineno=1))
    assert len(h.sent) == 3


def test_same_exception_logged_from_two_places_deduped():
    """同一个异常会被记录两次:中间件记一次再 re-raise,全局处理器又记一次。
    两处 module:lineno 不同,只能靠"异常本身"去重 —— 否则每个 500 推两条。"""
    import sys
    try:
        raise ValueError("Data too long for column 'image'")
    except ValueError:
        exc_info = sys.exc_info()

    h = _CapturingHandler(WEBHOOK)
    h.emit(_record(module="app.core.middleware", lineno=31, exc_info=exc_info))
    h.emit(_record(module="app.core.exceptions", lineno=54, exc_info=exc_info))
    assert len(h.sent) == 1, "同一个异常的两次记录被当成两个问题,会重复告警"


def test_different_exceptions_not_merged():
    """不同异常不能被误合并 —— 用异常消息区分同类型的不同错误"""
    import sys
    infos = []
    for msg in ("boom-A", "boom-B"):
        try:
            raise ValueError(msg)
        except ValueError:
            infos.append(sys.exc_info())

    h = _CapturingHandler(WEBHOOK)
    for info in infos:
        h.emit(_record(exc_info=info))
    assert len(h.sent) == 2


# ===== 限流 =====


def test_rate_limit_drops_extra(monkeypatch):
    """全局每分钟上限:超出直接丢弃,不让一个循环刷爆群"""
    monkeypatch.setattr(alert, "_RATE_LIMIT_PER_MINUTE", 3)
    h = _CapturingHandler(WEBHOOK)
    for i in range(10):
        h.emit(_record(lineno=i))  # 每次都换位置,绕过去重,只剩限流生效
    assert len(h.sent) == 3


# ===== 飞书签名 =====


def test_sign_is_second_level_timestamp():
    """飞书要求秒级时间戳;用毫秒会验签失败"""
    sig = FeishuAlertHandler(WEBHOOK, secret="s3cret")._sign()
    assert set(sig) == {"timestamp", "sign"}
    assert sig["timestamp"].isdigit() and len(sig["timestamp"]) == 10


def test_no_signature_without_secret():
    """没配密钥就不带签名(机器人安全设置可能选的是关键词白名单)"""
    assert FeishuAlertHandler(WEBHOOK)._sign() == {}


def test_payload_structure():
    """飞书自定义机器人的消息体格式"""
    p = FeishuAlertHandler(WEBHOOK, secret="s3cret", keyword="告警")._payload("hello")
    assert p["msg_type"] == "text"
    assert p["content"] == {"text": "hello"}
    assert "timestamp" in p and "sign" in p


def test_keyword_prefixed_into_message():
    """「自定义关键词」安全设置要求消息正文包含该词"""
    text = FeishuAlertHandler(WEBHOOK, keyword="告警")._format(_record())
    assert text.startswith("【告警】")


def test_format_contains_location_and_exception():
    """消息里要能一眼看出错在哪、错是什么"""
    try:
        raise ValueError("Data too long for column 'image'")
    except ValueError:
        import sys
        rec = _record(exc_info=sys.exc_info())
    text = FeishuAlertHandler(WEBHOOK)._format(rec)
    assert "app.services.demo:42" in text
    assert "ValueError" in text


# ===== 旁路铁律:告警失败绝不影响业务 =====


def test_send_failure_is_swallowed(monkeypatch):
    """发送失败只记本地日志,不向上抛"""
    h = FeishuAlertHandler(WEBHOOK)

    def _boom(text):
        raise RuntimeError("network down")

    monkeypatch.setattr(h, "_send_sync", _boom)
    h.emit(_record())  # 不应抛出


def test_unexpected_internal_error_is_swallowed(monkeypatch):
    """handler 内部任何意外异常都不能冒泡到业务代码"""
    h = FeishuAlertHandler(WEBHOOK)

    def _boom(_fingerprint):
        raise ValueError("内部错误")

    monkeypatch.setattr(h, "_allow", _boom)
    h.emit(_record())  # 不应抛出


# ===== 异步路径 =====


async def test_emit_uses_event_loop_when_available():
    """有事件循环时走 create_task,不阻塞调用方"""
    h = _CapturingHandler(WEBHOOK)
    h.emit(_record())
    assert h.sent == []      # emit 立即返回,此刻还没发
    await asyncio.sleep(0)   # 让任务跑一轮
    assert len(h.sent) == 1
