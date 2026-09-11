# -*- coding: utf-8 -*-
"""验证多 worker 部署下 WebSocket 跨进程推送。

原理:WS 连接落在某个 worker 进程,而推送可能由另一个 worker 发出;
      若经 Redis Pub/Sub 广播,连接方仍能收到 → 验证通过。

用法: python scripts/verify_ws_multiprocess.py
"""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx  # noqa: E402
import websockets  # noqa: E402

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000"


async def ws_client(sid: str, received: list, ready: asyncio.Event):
    """连接并收集消息(用 sid 区分不同客户端)"""
    async with websockets.connect(f"{WS}/ws/{sid}") as ws:
        ready.set()
        try:
            while True:
                raw = await asyncio.wait_for(ws.recv(), timeout=8)
                received.append(json.loads(raw))
        except (asyncio.TimeoutError, Exception):
            pass


async def admin_login():
    async with httpx.AsyncClient(timeout=15) as c:
        cap = (await c.get(f"{BASE}/admin/captcha")).json()
        r = await c.post(f"{BASE}/admin/employee/login", json={
            "username": "admin", "password": "123456",
            "captchaUuid": cap["data"]["uuid"], "captchaCode": cap["data"].get("code", ""),
        })
        return r.json()["data"]["token"]


async def main():
    # 两个用户端连接(可能落在不同 worker)
    received = []
    ready1, ready2 = asyncio.Event(), asyncio.Event()
    t1 = asyncio.create_task(ws_client("user-9991-verify", received, ready1))
    t2 = asyncio.create_task(ws_client("user-9992-verify", received, ready2))
    await asyncio.wait_for(asyncio.gather(ready1.wait(), ready2.wait()), timeout=10)
    await asyncio.sleep(1)  # 等订阅就绪

    token = await admin_login()
    async with httpx.AsyncClient(timeout=15) as c:
        h = {"token": token}
        await c.put(f"{BASE}/admin/shop/0", headers=h)   # 打烊 → 推 type=4 给所有用户端
        await asyncio.sleep(2)
        await c.put(f"{BASE}/admin/shop/1", headers=h)   # 恢复营业

    await asyncio.sleep(2)
    t1.cancel(); t2.cancel()

    types = [m.get("type") for m in received]
    print(f"收到消息数: {len(received)},类型分布: {types}")
    ok = 4 in types  # type=4 = 店铺状态变更
    print(f"跨进程推送: {'✅ 通过(收到 type=4 推送)' if ok else '❌ 未收到推送'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
