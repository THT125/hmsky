"""C端:联系商家(在线客服聊天)/user/chat"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.schemas.business import ChatMessageIn
from app.services import chat_service

router = APIRouter(prefix="/user/chat", tags=["C端-联系商家"])


@router.get("/messages", dependencies=[Depends(get_current_user)])
async def messages(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    查询当前用户与商家的聊天记录

    参数:
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 消息列表(按时间升序)。
    """
    return ok(await chat_service.get_messages(db, user_id))


@router.post("/messages", dependencies=[Depends(get_current_user)])
async def send(body: ChatMessageIn, db: AsyncSession = Depends(get_db),
               user_id: int = Depends(get_current_user)):
    """
    发送消息给商家

    参数:
    - body (ChatMessageIn): 消息参数模型,包含 content 内容。

    返回:
    - Result: 发送成功,实时推送到管理端。
    """
    return ok(await chat_service.send_user_message(db, user_id, body.content))


@router.post("/read", dependencies=[Depends(get_current_user)])
async def mark_read(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    标记已读:进入聊天页时调用,把商家回复的未读消息置为已读

    返回:
    - Result: 操作成功。
    """
    await chat_service.mark_read(db, user_id, reader="user")
    return ok()
