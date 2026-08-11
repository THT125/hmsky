"""WebSocket 服务:订单状态推送(原项目 /ws/{sid})
type: 1新订单推送管理端, 2催单推送管理端, 3订单状态变更推送用户端, 4店铺状态变更, 5菜单变更
"""
import json
from typing import Optional

from fastapi import WebSocket

from app.websocket.manager import WebSocketManager

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


async def websocket_endpoint(websocket: WebSocket, sid: str):
    await websocket.accept()
    ws_manager.connect(sid, websocket)
    try:
        while True:
            await websocket.receive_text()  # 保持连接,忽略客户端消息
    except Exception:
        pass
    finally:
        ws_manager.disconnect(sid)
