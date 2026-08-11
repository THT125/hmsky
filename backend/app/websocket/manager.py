"""WebSocket 连接管理(等价于原项目 WebSocketServer 的 SESSIONS map)
连接 sid 约定:
- admin-*           管理端
- user-{userId}-*   用户端(带用户 id,支持按用户定向推送)
"""
from typing import Dict, Optional

from fastapi import WebSocket


class WebSocketManager:
    def __init__(self):
        self._sessions: Dict[str, WebSocket] = {}

    def connect(self, sid: str, websocket: WebSocket):
        self._sessions[sid] = websocket

    def disconnect(self, sid: str):
        self._sessions.pop(sid, None)

    async def send_to_all(self, message: str, target: str = "admin", user_id: Optional[int] = None):
        """向指定端的所有连接广播消息。
        target: admin(管理端) / user(用户端) / all(全部)
        user_id: 指定后仅推送给该用户(user-{userId}-* 前缀)的连接;None 为广播该端全部。
        """
        prefix = f"user-{user_id}-" if (target == "user" and user_id is not None) else None
        for sid, ws in list(self._sessions.items()):
            try:
                is_user = sid.startswith("user-")
                if target == "admin" and is_user:
                    continue
                if target == "user" and not is_user:
                    continue
                if prefix is not None and not sid.startswith(prefix):
                    continue
                await ws.send_text(message)
            except Exception:
                pass
