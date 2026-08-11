"""管理端:店铺营业状态 /admin/shop"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_admin
from app.services import shop_service
from app.websocket.ws import push_shop_status

router = APIRouter(prefix="/admin/shop", tags=["店铺操作"])


@router.get("/status", dependencies=[Depends(get_current_admin)])
async def get_status(db: AsyncSession = Depends(get_db)):
    """
    获取营业状态

    参数:
    - db (Session): 数据库会话。

    返回:
    - Result: 1营业 0打烊。
    """
    return ok(await shop_service.get_status(db))


@router.put("/{status}", dependencies=[Depends(get_current_admin)])
async def set_status(status: int, db: AsyncSession = Depends(get_db)):
    """
    设置营业状态

    参数:
    - status (int): 目标状态,1营业 0打烊。
    - db (Session): 数据库会话。

    返回:
    - Result: 操作成功(推送状态变更给用户端)。
    """
    await shop_service.set_status(db, status)
    # WebSocket 推送店铺状态变更给用户端(type=4)
    await push_shop_status(status)
    return ok()
