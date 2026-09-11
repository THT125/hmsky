"""WebSocket 连接管理(支持多 worker / 多副本部署)

连接 sid 约定:
- admin-*           管理端
- user-{userId}-*   用户端(带用户 id,支持按用户定向推送)

多副本设计:
    每个 worker 进程维护自己的连接表(_sessions);
    推送时把消息发布到 Redis 频道(ws:broadcast),所有 worker 的订阅者收到后
    各推给【本进程内】匹配的连接 —— 用户连接落在哪个 worker 都能收到消息。
    Redis 不可用时降级为"仅推本进程连接"(单 worker 场景不受影响)。
"""
import asyncio
import json
import logging
from typing import Dict, Optional

from fastapi import WebSocket

logger = logging.getLogger("uvicorn.error")

WS_CHANNEL = "ws:broadcast"


def _match(sid: str, target: str, user_id: Optional[int]) -> bool:
    """判断连接 sid 是否匹配推送目标"""
    is_user = sid.startswith("user-")
    if target == "admin" and is_user:
        return False
    if target == "user" and not is_user:
        return False
    if target == "user" and user_id is not None:
        return sid.startswith(f"user-{user_id}-")
    return True


class WebSocketManager:
    def __init__(self):
        self._sessions: Dict[str, WebSocket] = {}
        self._listener_task: Optional[asyncio.Task] = None

    def connect(self, sid: str, websocket: WebSocket):
        self._sessions[sid] = websocket

    def disconnect(self, sid: str):
        self._sessions.pop(sid, None)

    # ===== 本地推送(仅本进程内的连接) =====

    async def send_local(self, message: str, target: str = "admin", user_id: Optional[int] = None):
        """向【本进程内】匹配的连接推送"""
        for sid, ws in list(self._sessions.items()):
            if not _match(sid, target, user_id):
                continue
            try:
                await ws.send_text(message)
            except Exception as e:
                logger.debug("向连接 %s 推送失败(连接可能已断开): %s", sid, e)

    # ===== 跨进程推送(Redis Pub/Sub) =====

    async def send_to_all(self, message: str, target: str = "admin", user_id: Optional[int] = None):
        """向指定端广播(跨 worker)。target: admin / user / all
        user_id: 指定后仅推给该用户(user-{userId}-* 前缀)的连接。
        """
        payload = json.dumps({"message": message, "target": target, "user_id": user_id})
        try:
            from app.core.redis import redis_publish

            await redis_publish(WS_CHANNEL, payload)
        except Exception as e:
            # Redis 不可用:降级为仅推本进程连接(单 worker 与降级场景下仍可用)
            logger.warning("WS 跨进程广播降级(仅本进程推送): %s", e)
            await self.send_local(message, target, user_id)

    async def listen(self):
        """订阅 Redis 频道,把消息分发给本进程内的连接(每个 worker 启动时运行)。

        断线自动重连;订阅到消息后统一走 send_local(含自己发布的,行为一致)。
        """
        from app.core.redis import get_redis

        while True:
            try:
                pubsub = get_redis().pubsub()
                await pubsub.subscribe(WS_CHANNEL)
                logger.info("WebSocket 跨进程订阅已启动: %s", WS_CHANNEL)
                async for msg in pubsub.listen():
                    if msg.get("type") != "message":
                        continue
                    try:
                        data = json.loads(msg["data"])
                        await self.send_local(data["message"], data.get("target", "admin"),
                                              data.get("user_id"))
                    except Exception as e:
                        logger.warning("分发 WS 消息失败: %s", e)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("WS 订阅异常,3 秒后重连: %s", e)
                await asyncio.sleep(3)

    def start_listener(self):
        """启动订阅协程(lifespan 中调用)"""
        if self._listener_task is None:
            self._listener_task = asyncio.create_task(self.listen())

    async def stop_listener(self):
        if self._listener_task is not None:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except (asyncio.CancelledError, Exception):
                pass
            self._listener_task = None
