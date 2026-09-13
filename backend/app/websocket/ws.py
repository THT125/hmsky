"""WebSocket 服务:订单状态推送(原项目 /ws/{sid})
type: 1新订单推送管理端, 2催单推送管理端, 3订单状态变更推送用户端, 4店铺状态变更, 5菜单变更, 6客服消息
"""
import json
import logging
from typing import Optional

from fastapi import WebSocket

from app.websocket.manager import WebSocketManager

logger = logging.getLogger("uvicorn.error")

ws_manager = WebSocketManager()


async def push_order_message(msg_type: int, order_id: int, content: str, target: str = "admin",
                             user_id: Optional[int] = None):
    """推送消息。type: 1新订单 2催单 3订单状态变更 4店铺状态变更 5菜单变更;target: admin/user
    user_id: 用户端定向推送时传目标用户 id(如 type=3 订单状态变更);None 为广播。
    """
    payload = json.dumps({"type": msg_type, "orderId": order_id, "content": content}, ensure_ascii=False)
    await ws_manager.send_to_all(payload, target=target, user_id=user_id)


async def push_shop_status(status: int):
    """店铺营业状态变更,推送用户端(type=4)"""
    await push_order_message(4, 0, "店铺已打烊" if status == 0 else "店铺已开始营业", target="user")


async def push_menu_update():
    """菜品/套餐/分类变更,推送用户端刷新菜单(type=5)"""
    await push_order_message(5, 0, "菜单已更新", target="user")


async def push_chat_message(target: str, user_id: Optional[int], payload: dict):
    """客服消息推送(type=6)。target=admin 推管理端;target=user + user_id 定向推指定用户。
    payload: {userId, senderType, senderId, content, createTime}
    """
    msg = {"type": 6, "content": payload.get("content", ""), "chat": payload}
    await ws_manager.send_to_all(json.dumps(msg, ensure_ascii=False, default=str), target=target, user_id=user_id)


async def websocket_endpoint(websocket: WebSocket, sid: str):
    await websocket.accept()
    ws_manager.connect(sid, websocket)
    # 连接/断开用 INFO 对称记录:排查连接泄漏时要靠这两个数对账。
    # 之前断开记的是 DEBUG(低于默认 INFO 级别),日志里只有 open 没有 close,
    # 排查时会被误读成"连接永不关闭"。
    logger.info("WebSocket 已连接 %s", sid)
    try:
        while True:
            await websocket.receive_text()  # 保持连接,忽略客户端消息
    except Exception as e:
        logger.debug("WebSocket 断开原因 %s: %s", sid, e)  # 客户端正常断开也会走这里,不刷 INFO
    finally:
        ws_manager.disconnect(sid)
        logger.info("WebSocket 已断开 %s", sid)
