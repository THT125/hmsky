"""管理端:客服消息(在线客服聊天)/admin/chat"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_admin
from app.schemas.business import ChatReplyIn
from app.services import chat_service

router = APIRouter(prefix="/admin/chat", tags=["客服消息"])


@router.get("/sessions", dependencies=[Depends(get_current_admin)])
async def sessions(db: AsyncSession = Depends(get_db)):
    """
    会话列表:按用户聚合(最后消息/未读数),时间倒序

    返回:
    - Result: [{userId, username, phone, lastContent, lastSender, lastTime, unread}]
    """
    server=await chat_service.list_sessions(db)
    return ok(server)


@router.get("/messages", dependencies=[Depends(get_current_admin)])
async def messages(userId: Optional[int] = Query(None, alias="userId"),
                   db: AsyncSession = Depends(get_db)):
    """
    查询某用户的会话消息

    参数:
    - userId (int): 用户id。

    返回:
    - Result: 消息列表(按时间升序)。
    """
    if userId is None:
        return ok([])
    server=await chat_service.get_messages(db, userId)
    return ok(server)


@router.post("/messages", dependencies=[Depends(get_current_admin)])
async def reply(body: ChatReplyIn, db: AsyncSession = Depends(get_db),
                emp_id: int = Depends(get_current_admin)):
    """
    回复用户消息

    参数:
    - body (ChatReplyIn): 回复参数模型,包含 userId 目标用户、content 内容。

    返回:
    - Result: 回复成功,实时定向推送给该用户。
    """
    server=await chat_service.send_admin_message(db, emp_id, body.user_id, body.content)
    return ok(server)


@router.post("/read", dependencies=[Depends(get_current_admin)])
async def mark_read(userId: int = Query(..., alias="userId"), db: AsyncSession = Depends(get_db)):
    """
    标记会话已读:把该用户发来的未读消息置为已读

    返回:
    - Result: 操作成功。
    """
    await chat_service.mark_read(db, userId, reader="admin")
    return ok()
