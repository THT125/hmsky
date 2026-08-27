"""客服聊天:用户↔商家双向消息(一个用户=一个会话,消息落库 + WS 实时通知)"""
from typing import Optional

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.models import ChatMessage, User
from app.websocket.ws import push_chat_message


async def send_user_message(db: AsyncSession, user_id: int, content: str) -> dict:
    """用户发送消息:存库(商家未读)+ WS 推送管理端"""
    content = (content or "").strip()
    if not content:
        raise BizException("消息内容不能为空")
    if len(content) > 500:
        raise BizException("消息内容过长(最多500字)")
    msg = ChatMessage(user_id=user_id, sender_type="user", sender_id=user_id,
                      content=content, read_status=0)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    payload = _to_dict(msg)
    await push_chat_message(target="admin", user_id=None, payload=payload)
    return payload


async def send_admin_message(db: AsyncSession, admin_id: int, user_id: int, content: str) -> dict:
    """商家回复:存库(用户未读)+ WS 定向推该用户"""
    content = (content or "").strip()
    if not content:
        raise BizException("消息内容不能为空")
    if len(content) > 500:
        raise BizException("消息内容过长(最多500字)")
    user = await db.get(User, user_id)
    if user is None:
        raise BizException("用户不存在")
    msg = ChatMessage(user_id=user_id, sender_type="admin", sender_id=admin_id,
                      content=content, read_status=0)
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    payload = _to_dict(msg)
    await push_chat_message(target="user", user_id=user_id, payload=payload)
    return payload


async def get_messages(db: AsyncSession, user_id: int) -> list:
    """某用户会话全部消息(按时间升序,时间旧→新)"""
    rows = (await db.execute(
        select(ChatMessage).where(ChatMessage.user_id == user_id)
        .order_by(ChatMessage.create_time.asc(), ChatMessage.id.asc())
    )).scalars().all()
    return [_to_dict(m) for m in rows]


async def list_sessions(db: AsyncSession) -> list:
    """管理端会话列表:按用户聚合(最后消息/最后时间/未读数=用户发来未读条数),时间倒序"""
    rows = (await db.execute(text("""
        SELECT m.user_id,
               m.content AS last_content,
               m.sender_type AS last_sender,
               m.create_time AS last_time,
               (SELECT COUNT(*) FROM chat_message c
                WHERE c.user_id = m.user_id AND c.sender_type = 'user' AND c.read_status = 0) AS unread
        FROM chat_message m
        WHERE m.id IN (SELECT MAX(id) FROM chat_message GROUP BY user_id)
        ORDER BY m.create_time DESC, m.id DESC
    """))).all()
    sessions = []
    for r in rows:
        user = await db.get(User, r.user_id)
        sessions.append({
            "userId": r.user_id,
            "username": user.username if user else "已注销用户",
            "phone": user.phone if user else None,
            "lastContent": r.last_content,
            "lastSender": r.last_sender,
            "lastTime": r.last_time,
            "unread": r.unread,
        })
    return sessions


async def mark_read(db: AsyncSession, user_id: int, reader: str):
    """标记已读:reader=admin 时把用户发来的消息置已读;reader=user 时把商家回复置已读"""
    if reader == "admin":
        cond = "sender_type = 'user'"
    else:
        cond = "sender_type = 'admin'"
    await db.execute(update(ChatMessage).where(
        ChatMessage.user_id == user_id, ChatMessage.read_status == 0
    ).where(text(cond)).values(read_status=1))
    await db.commit()


def _to_dict(model: ChatMessage) -> dict:
    return {
        "id": model.id,
        "userId": model.user_id,
        "senderType": model.sender_type,
        "senderId": model.sender_id,
        "content": model.content,
        "readStatus": model.read_status,
        "createTime": model.create_time,
    }
