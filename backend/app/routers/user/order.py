"""C端:订单 /user/order"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import page_result
from app.core.result import ok
from app.core.security import get_current_user
from app.schemas.business import OrdersPaymentIn, OrdersSubmitIn
from app.services import order_service

router = APIRouter(prefix="/user/order", tags=["C端-订单"])


@router.post("/submit")
async def submit(body: OrdersSubmitIn, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    用户下单

    参数:
    - body (OrdersSubmitIn): 下单参数模型,包含 addressBookId 地址id、amount 金额、deliveryStatus 配送状态、packAmount 打包费、payMethod 支付方式、remark 备注、tablewareNumber 餐具数量等。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: {id 订单id, orderNumber 订单号, orderAmount 订单金额, orderTime 下单时间}。
    """
    return ok(await order_service.submit(db, user_id, body))


@router.put("/payment")
async def payment(body: OrdersPaymentIn, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    订单支付(模拟支付)

    参数:
    - body (OrdersPaymentIn): 支付参数模型,包含 orderNumber 订单号、payMethod 支付方式。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 支付成功(模拟环境直接置为已支付)。
    """
    await order_service.payment(db, user_id, body.order_number)
    return ok()


@router.get("/historyOrders")
async def history_orders(page: int = Query(1), pageSize: int = Query(10, alias="pageSize"),
                         status: Optional[int] = None,
                         db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    历史订单查询

    参数:
    - page (int): 页码,默认1。
    - pageSize (int): 每页条数,默认10。
    - status (int, 可选): 订单状态过滤。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 分页结果 {total, records},每条含 orderDetailList 明细。
    """
    total, rows = await order_service.history_orders(db, user_id, page, pageSize, status)
    return ok(page_result(total, [await order_service.build_order_vo(db, o) for o in rows]))


@router.get("/orderDetail/{order_id}")
async def order_detail(order_id: int, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    查询订单详情

    参数:
    - order_id (int): 订单id。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 订单详情,含 orderDetailList 明细列表。
    """
    order = await order_service.get_user_order_detail(db, user_id, order_id)
    return ok(await order_service.build_order_vo(db, order))


@router.put("/cancel/{order_id}")
async def cancel(order_id: int, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    取消订单

    参数:
    - order_id (int): 订单id。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 取消成功(仅待付款/待接单状态可取消)。
    """
    await order_service.user_cancel(db, user_id, order_id)
    return ok()


@router.post("/repetition/{order_id}")
async def repetition(order_id: int, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    再来一单

    参数:
    - order_id (int): 订单id。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 操作成功(原订单菜品重新加入购物车)。
    """
    await order_service.repeat_order(db, user_id, order_id)
    return ok()


@router.get("/reminder/{order_id}")
async def reminder(order_id: int, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    催单

    参数:
    - order_id (int): 订单id。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 催单成功(通过 WebSocket 推送管理端)。
    """
    await order_service.remind(db, user_id, order_id)
    return ok()
