"""管理端:订单管理 /admin/order"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import page_result
from app.core.result import ok
from app.core.security import get_current_admin
from app.schemas.business import OrderCancelIn, OrderConfirmIn, OrderRejectionIn
from app.services import order_service

router = APIRouter(prefix="/admin/order", tags=["订单管理"])


@router.get("/conditionSearch", dependencies=[Depends(get_current_admin)])
async def condition_search(page: int = Query(1), pageSize: int = Query(10, alias="pageSize"),
                           status: Optional[int] = None, number: Optional[str] = None,
                           phone: Optional[str] = None, beginTime: Optional[str] = Query(None, alias="beginTime"),
                           endTime: Optional[str] = Query(None, alias="endTime"),
                           db: AsyncSession = Depends(get_db)):
    """
    订单搜索

    参数:
    - page (int): 页码,默认1。
    - pageSize (int): 每页条数,默认10。
    - status (int, 可选): 订单状态,1待付款 2待接单 3已接单 4派送中 5已完成 6已取消。
    - number (str, 可选): 订单号,模糊查询。
    - phone (str, 可选): 手机号,模糊查询。
    - beginTime (str, 可选): 下单开始时间。
    - endTime (str, 可选): 下单结束时间。
    - db (Session): 数据库会话。

    返回:
    - Result: 分页结果 {total, records},每条含 orderDishes 菜品拼接字符串。
    """
    total, rows = await order_service.condition_search(db, page, pageSize, status, number, phone, beginTime, endTime)
    return ok(page_result(total, [await order_service.build_order_vo(db, o) for o in rows]))


@router.get("/statistics", dependencies=[Depends(get_current_admin)])
async def statistics(db: AsyncSession = Depends(get_db)):
    """
    各个状态的订单数量统计

    参数:
    - db (Session): 数据库会话。

    返回:
    - Result: {toBeConfirmed 待接单, confirmed 待派送, deliveryInProgress 派送中}。
    """
    return ok(await order_service.statistics(db))


@router.get("/details/{order_id}", dependencies=[Depends(get_current_admin)])
async def details(order_id: int, db: AsyncSession = Depends(get_db)):
    """
    查询订单详情

    参数:
    - order_id (int): 订单id。

    返回:
    - Result: 订单详情,含 orderDetailList 明细列表。
    """
    order = await order_service.get_order_by_id(db, order_id)
    return ok(await order_service.build_order_vo(db, order))


@router.put("/confirm", dependencies=[Depends(get_current_admin)])
async def confirm(body: OrderConfirmIn, db: AsyncSession = Depends(get_db)):
    """
    接单

    参数:
    - body (OrderConfirmIn): 接单参数模型,包含 id 订单id。

    返回:
    - Result: 操作成功(推送状态变更给用户端)。
    """
    await order_service.confirm(db, body.id)
    return ok()


@router.put("/rejection", dependencies=[Depends(get_current_admin)])
async def rejection(body: OrderRejectionIn, db: AsyncSession = Depends(get_db)):
    """
    拒单

    参数:
    - body (OrderRejectionIn): 拒单参数模型,包含 id 订单id、rejectionReason 拒单原因。

    返回:
    - Result: 操作成功(推送状态变更给用户端)。
    """
    await order_service.rejection(db, body.id, body.rejection_reason)
    return ok()


@router.put("/cancel", dependencies=[Depends(get_current_admin)])
async def cancel(body: OrderCancelIn, db: AsyncSession = Depends(get_db)):
    """
    取消订单

    参数:
    - body (OrderCancelIn): 取消订单参数模型,包含 id 订单id、cancelReason 取消原因。

    返回:
    - Result: 操作成功(推送状态变更给用户端)。
    """
    await order_service.admin_cancel(db, body.id, body.cancel_reason)
    return ok()


@router.put("/delivery/{order_id}", dependencies=[Depends(get_current_admin)])
async def delivery(order_id: int, db: AsyncSession = Depends(get_db)):
    """
    派送订单

    参数:
    - order_id (int): 订单id。

    返回:
    - Result: 操作成功(推送状态变更给用户端)。
    """
    await order_service.delivery(db, order_id)
    return ok()


@router.put("/complete/{order_id}", dependencies=[Depends(get_current_admin)])
async def complete(order_id: int, db: AsyncSession = Depends(get_db)):
    """
    完成订单

    参数:
    - order_id (int): 订单id。

    返回:
    - Result: 操作成功(推送状态变更给用户端)。
    """
    await order_service.complete(db, order_id)
    return ok()
