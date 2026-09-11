# -*- coding: utf-8 -*-
"""压测脚本:验证高并发下的正确性与性能。

场景:
  menu    菜单查询(缓存读)   —— 测缓存命中吞吐
  coupon  抢券(Redis 闸门)   —— 核心:验证"不超发"

用法:
  python scripts/loadtest.py --scenario coupon --users 500 --stock 100
  python scripts/loadtest.py --scenario menu --concurrency 100 --requests 5000

设计说明:
  · 场景准备(建用户/发 token)直连应用内部(DB + Redis + JWT),
    避免准备阶段走 HTTP 拖慢压测,也绕开验证码;
  · 压测本身走真实 HTTP 接口(测的是生产路径);
  · 结束后校验 MySQL/Redis 库存,并清理测试数据。
"""
import argparse
import asyncio
import random
import statistics
import sys
import time
import uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
from sqlalchemy import delete, func, select, text  # noqa: E402

from app.core.config import USER_TTL  # noqa: E402
from app.core.database import AsyncSessionLocal  # noqa: E402
from app.core.redis import (  # noqa: E402
    COUPON_STOCK_PREFIX,
    redis_delete,
    redis_get,
    redis_setex,
)
from app.core.security import SESSION_USER_PREFIX, create_user_token, new_jti  # noqa: E402
from app.models import Coupon, User, UserCoupon  # noqa: E402

BASE = "http://127.0.0.1:8000"
RUN_ID = uuid.uuid4().hex[:6]


# ===== 指标采集 =====

class Metrics:
    def __init__(self):
        self.latencies = []
        self.codes = {}
        self.errors = []
        self.biz_reject = 0      # HTTP 200 但 code=0(业务拒绝,属预期)
        self.success = 0

    def record(self, cost: float, code: int):
        self.latencies.append(cost)
        self.codes[code] = self.codes.get(code, 0) + 1

    def report(self, title: str, duration: float):
        total = len(self.latencies)
        if not total:
            print("无请求数据")
            return
        s = sorted(self.latencies)
        p = lambda q: s[min(int(len(s) * q), len(s) - 1)] * 1000  # noqa: E731
        print(f"\n===== 压测结果: {title} =====")
        print(f"总请求:     {total}")
        print(f"成功:       {self.success}")
        print(f"业务拒绝:   {self.biz_reject}  (库存不足/已领取等预期响应)")
        print(f"异常:       {len(self.errors)}")
        print(f"耗时:       {duration:.2f}s")
        print(f"QPS:        {total / duration:.1f}")
        print(f"延迟 P50:   {p(0.50):.1f} ms")
        print(f"延迟 P90:   {p(0.90):.1f} ms")
        print(f"延迟 P95:   {p(0.95):.1f} ms")
        print(f"延迟 P99:   {p(0.99):.1f} ms")
        print(f"延迟 最大:  {max(s) * 1000:.1f} ms")
        print(f"HTTP 状态分布: {self.codes}")
        if self.errors:
            print("异常样例:")
            for e in self.errors[:5]:
                print(f"  - {e}")


async def _fire(client, method, path, headers=None, json=None, metrics=None):
    """发起一次请求并记录指标"""
    t0 = time.perf_counter()
    try:
        r = await client.request(method, BASE + path, headers=headers, json=json)
        cost = time.perf_counter() - t0
        metrics.record(cost, r.status_code)
        body = r.json()
        if body.get("code") == 1:
            metrics.success += 1
        else:
            metrics.biz_reject += 1
        return body
    except Exception as e:
        cost = time.perf_counter() - t0
        metrics.record(cost, -1)
        metrics.errors.append(f"{path}: {e}")
        return None


# ===== 测试数据准备(直连 DB/Redis,快) =====

async def prepare_users(count: int) -> list:
    """批量创建压测用户 + JWT + Redis 会话,返回 [(user_id, token), ...]"""
    from app.utils.password import hash_password

    dummy_pwd = hash_password("loadtest123")  # 只哈希一次,全部用户复用(压测用户不校验密码)
    async with AsyncSessionLocal() as db:
        max_id = (await db.scalar(select(func.max(User.id)))) or 0
        base_seq = max_id + 1
        for i in range(count):
            db.add(User(
                username=f"lt_{RUN_ID}_{i}",
                password=dummy_pwd,
                phone=f"138{base_seq + i:08d}",
            ))
        await db.commit()
        # 重新查询拿到自增 id
        rows = (await db.execute(
            select(User.id, User.username).where(User.username.like(f"lt_{RUN_ID}_%"))
        )).all()

    # 生成 token + 写 Redis 会话(模拟已登录)
    tokens = []
    for uid, uname in rows:
        jti = new_jti()
        tokens.append((uid, create_user_token(uid, uname, jti), jti))
    for uid, _, jti in tokens:
        await redis_setex(f"{SESSION_USER_PREFIX}{uid}", USER_TTL // 1000, jti)
    return [(uid, tok) for uid, tok, _ in tokens]


async def prepare_coupon(stock: int) -> int:
    """创建一个压测用券,返回 coupon_id。

    预热与真实流程一致(管理端建券会同步预热存量 + 券信息缓存):
    否则 500 请求会同时缓存 miss → 全部回源 MySQL(缓存击穿)。
    """
    from app.services.coupon_service import _cache_coupon_info

    async with AsyncSessionLocal() as db:
        now = datetime.now()
        c = Coupon(
            name=f"压测券_{RUN_ID}", type=1, amount=10, min_amount=0,
            total=stock, stock=stock, per_user_limit=1, valid_days=1,
            start_time=now - timedelta(hours=1), end_time=now + timedelta(days=1),
            status=1,
        )
        db.add(c)
        await db.commit()
        await db.refresh(c)
        cid = c.id
        await _cache_coupon_info(c)  # 预热券信息缓存(与管理端建券一致)
    # 预热 Redis 存量(与业务一致)
    await redis_setex(f"{COUPON_STOCK_PREFIX}{cid}", 86400, str(stock))
    return cid


async def cleanup(user_ids: list, coupon_id: int | None):
    """清理压测数据(用户/持有记录/券/Redis key)"""
    async with AsyncSessionLocal() as db:
        if coupon_id:
            await db.execute(delete(UserCoupon).where(UserCoupon.coupon_id == coupon_id))
            await db.execute(delete(Coupon).where(Coupon.id == coupon_id))
        if user_ids:
            await db.execute(delete(User).where(User.id.in_(user_ids)))
        await db.commit()
    if coupon_id:
        await redis_delete(f"{COUPON_STOCK_PREFIX}{coupon_id}")
        # 限领标记(券维度:coupon:user:{cid}:{uid})
        for uid in user_ids:
            await redis_delete(f"coupon:user:{coupon_id}:{uid}")
    for uid in user_ids:
        await redis_delete(f"{SESSION_USER_PREFIX}{uid}")
    print(f"[清理] 用户 {len(user_ids)} 个,券 {coupon_id}")


# ===== 场景 1:菜单查询(缓存读) =====

async def scenario_menu(concurrency: int, requests: int, category_id: int):
    print(f"\n[场景] 菜单查询  并发={concurrency}  总请求={requests}")
    users = await prepare_users(1)
    _, token = users[0]
    headers = {"authentication": token}
    limits = httpx.Limits(max_connections=concurrency + 50, max_keepalive_connections=concurrency)
    sem = asyncio.Semaphore(concurrency)
    metrics = Metrics()

    async def worker():
        async with sem:
            await _fire(client, "GET", f"/user/dish/list?categoryId={category_id}",
                        headers=headers, metrics=metrics)

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        await asyncio.gather(*[worker() for _ in range(requests)])
    duration = time.perf_counter() - t0

    metrics.report("菜单查询(缓存读)", duration)
    await cleanup([u for u, _ in users], None)


# ===== 场景 2:抢券(核心:验证不超发) =====

async def scenario_coupon(users_count: int, stock: int):
    print(f"\n[场景] 抢券  并发用户={users_count}  券库存={stock}")
    coupon_id = await prepare_coupon(stock)
    users = await prepare_users(users_count)
    print(f"[准备] 券 id={coupon_id} 库存={stock},用户 {len(users)} 个已就绪")

    limits = httpx.Limits(max_connections=users_count + 50, max_keepalive_connections=users_count)
    metrics = Metrics()
    sem = asyncio.Semaphore(users_count)  # 全部并发

    async def worker(uid, token):
        async with sem:
            await _fire(client, "POST", f"/user/coupon/grab/{coupon_id}",
                        headers={"authentication": token}, metrics=metrics)

    t0 = time.perf_counter()
    async with httpx.AsyncClient(timeout=30, limits=limits) as client:
        await asyncio.gather(*[worker(uid, tok) for uid, tok in users])
    duration = time.perf_counter() - t0

    metrics.report("抢券(Redis 闸门防超发)", duration)

    # ===== 数据校验:是否超发 =====
    async with AsyncSessionLocal() as db:
        db_stock = (await db.scalar(select(Coupon.stock).where(Coupon.id == coupon_id))) or 0
        claimed = (await db.scalar(
            select(func.count(UserCoupon.id)).where(UserCoupon.coupon_id == coupon_id))) or 0
    try:
        redis_stock = int(await redis_get(f"{COUPON_STOCK_PREFIX}{coupon_id}") or -1)
    except Exception:
        redis_stock = -1

    expected = min(users_count, stock)
    print("\n----- 数据一致性校验 -----")
    print(f"MySQL 库存:   {db_stock}  (初始 {stock})")
    print(f"Redis 库存:   {redis_stock}")
    print(f"实际领取记录: {claimed}  (预期 {expected})")
    print(f"接口成功数:   {metrics.success}")
    oversold = claimed > stock
    print(f"是否超发:     {'❌ 是(严重!)' if oversold else '✅ 否'}")
    consistent = (db_stock == stock - claimed) and (claimed == metrics.success) and (claimed == expected)
    print(f"数据一致性:   {'✅ 通过' if consistent else '⚠️ 存在偏差(见上方数字)'}")

    await cleanup([u for u, _ in users], coupon_id)


# ===== 入口 =====

async def main():
    ap = argparse.ArgumentParser(description="苍穹外卖压测")
    ap.add_argument("--scenario", choices=["menu", "coupon"], default="coupon")
    ap.add_argument("--concurrency", type=int, default=100, help="menu 场景并发数")
    ap.add_argument("--requests", type=int, default=2000, help="menu 场景总请求数")
    ap.add_argument("--category-id", type=int, default=1, help="menu 场景分类 id")
    ap.add_argument("--users", type=int, default=500, help="coupon 场景并发用户数")
    ap.add_argument("--stock", type=int, default=100, help="coupon 场景券库存")
    args = ap.parse_args()

    # 连通性检查
    try:
        async with httpx.AsyncClient(timeout=5) as c:
            await c.get(BASE + "/docs")
    except Exception:
        print(f"无法连接后端 {BASE},请先启动服务")
        return 1

    if args.scenario == "menu":
        await scenario_menu(args.concurrency, args.requests, args.category_id)
    else:
        await scenario_coupon(args.users, args.stock)

    # 优雅关闭连接池(避免退出时 aiomysql 清理告警)
    from app.core.database import engine
    await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
