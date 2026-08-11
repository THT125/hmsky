"""管理端:工作台 /admin/workspace"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_admin
from app.services import workspace_service

router = APIRouter(prefix="/admin/workspace", tags=["工作台"])


@router.get("/businessData", dependencies=[Depends(get_current_admin)])
async def business_data(db: AsyncSession = Depends(get_db)):
    """
    查询今日运营数据

    参数:
    - db (Session): 数据库会话。

    返回:
    - Result: {turnover 营业额, validOrderCount 有效订单数, orderCompletionRate 订单完成率, unitPrice 平均客单价, newUsers 新增用户数}。
    """
    return ok(await workspace_service.business_data(db))


@router.get("/overviewOrders", dependencies=[Depends(get_current_admin)])
async def overview_orders(db: AsyncSession = Depends(get_db)):
    """
    查询订单管理数据

    参数:
    - db (Session): 数据库会话。

    返回:
    - Result: {allOrders 全部, waitingOrders 待接单, deliveredOrders 待派送, completedOrders 已完成, cancelledOrders 已取消}。
    """
    return ok(await workspace_service.overview_orders(db))


@router.get("/overviewDishes", dependencies=[Depends(get_current_admin)])
async def overview_dishes(db: AsyncSession = Depends(get_db)):
    """
    查询菜品总览

    参数:
    - db (Session): 数据库会话。

    返回:
    - Result: {sold 已启售数量, discontinued 已停售数量}。
    """
    return ok(await workspace_service.overview_dishes(db))


@router.get("/overviewSetmeals", dependencies=[Depends(get_current_admin)])
async def overview_setmeals(db: AsyncSession = Depends(get_db)):
    """
    查询套餐总览

    参数:
    - db (Session): 数据库会话。

    返回:
    - Result: {sold 已启售数量, discontinued 已停售数量}。
    """
    return ok(await workspace_service.overview_setmeals(db))
