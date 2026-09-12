"""订单业务(规则与原 OrderServiceImpl + OrderMapper 一致)"""
import logging
import random
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException, OrderStateException

logger = logging.getLogger("uvicorn.error")
from app.core.redis import (
    HOT_DISHES_KEY,
    HOT_SETMEALS_KEY,
    STOCK_DISH_PREFIX,
    STOCK_SETMEAL_PREFIX,
    redis_incrby,
    redis_release_lock,
    redis_setnx,
    redis_stock_deduct,
    redis_zincrby,
)
from app.models import AddressBook, Category, Dish, OrderDetail, Orders, Setmeal, ShoppingCart, User
from app.schemas.business import OrdersSubmitIn
from app.services.order_state import OrderStateMachine
from app.services.shop_service import get_status
from app.utils.baidu_distance import get_distance
from app.websocket.ws import push_order_message

DELIVERY_FEE = 6  # 固定配送费
ORDER_LOCK_TTL = 5  # 下单防重锁超时(秒):下单流程远小于 5s,崩溃自动释放


async def _redis_incr_stock(key: str, n: int):
    """Redis 库存同步回补(失败降级,MySQL 为权威)"""
    try:
        await redis_incrby(key, n)
    except Exception as e:
        logger.warning("Redis库存回补降级(MySQL为权威,展示可能短暂滞后): %s", e)


async def _update_hot_sales(db: AsyncSession, order: Orders, delta: int):
    """热销榜销量:支付成功 +delta,已支付退款 -delta(MySQL 权威,Redis 加速,失败降级)"""
    details = list((await db.execute(
        select(OrderDetail).where(OrderDetail.order_id == order.id)
    )).scalars().all())
    for d in details:
        try:
            if d.dish_id is not None:
                await redis_zincrby(HOT_DISHES_KEY, delta * d.number, d.dish_id)
            elif d.setmeal_id is not None:
                await redis_zincrby(HOT_SETMEALS_KEY, delta * d.number, d.setmeal_id)
        except Exception as e:
            logger.warning("热销榜销量更新降级: %s", e)


async def _deduct_stock(db: AsyncSession, cart_list: list) -> None:
    """下单预扣库存(同一事务内,失败整单回滚)。

    分层防超卖:
    1. Redis Lua 原子扣减抢购资格(单线程串行,挡住 99% 并发请求)
       - -1:已抢光,直接拒绝
       - 0:跳过(不限量无 key / Redis 宕机降级)→ 交给 MySQL 兜底
    2. MySQL 原子扣减(权威,UPDATE ... WHERE stock >= n,行数=1 才成功)
       - 失败(理论罕见,Redis 与库不一致):回补 Redis 保持两边一致
    """
    for item in cart_list:
        if item.dish_id is not None:
            key = f"{STOCK_DISH_PREFIX}{item.dish_id}"
            redis_ok = await redis_stock_deduct(key, item.number)
            if redis_ok == -1:
                raise BizException(f"菜品库存不足: {item.name}")
            stock = await db.scalar(select(Dish.stock).where(Dish.id == item.dish_id))
            if stock is None:
                continue  # 不限量
            r = await db.execute(
                text("UPDATE dish SET stock = stock - :n WHERE id = :id AND stock >= :n"),
                {"n": item.number, "id": item.dish_id},
            )
            if r.rowcount != 1:
                if redis_ok > 0:  # Redis 已扣,回补保持一致
                    await _redis_incr_stock(key, item.number)
                raise BizException(f"菜品库存不足: {item.name}")
        elif item.setmeal_id is not None:
            key = f"{STOCK_SETMEAL_PREFIX}{item.setmeal_id}"
            redis_ok = await redis_stock_deduct(key, item.number)
            if redis_ok == -1:
                raise BizException(f"套餐库存不足: {item.name}")
            stock = await db.scalar(select(Setmeal.stock).where(Setmeal.id == item.setmeal_id))
            if stock is None:
                continue  # 不限量
            r = await db.execute(
                text("UPDATE setmeal SET stock = stock - :n WHERE id = :id AND stock >= :n"),
                {"n": item.number, "id": item.setmeal_id},
            )
            if r.rowcount != 1:
                if redis_ok > 0:  # Redis 已扣,回补保持一致
                    await _redis_incr_stock(key, item.number)
                raise BizException(f"套餐库存不足: {item.name}")


async def _restore_stock(db: AsyncSession, order: Orders) -> None:
    """取消/拒单/超时回补库存。
    幂等:先原子抢占 orders.stock_restored(0→1),抢到才回补——
    防超时任务与用户取消并发同一订单导致双回补。
    """
    claimed = await db.execute(
        text("UPDATE orders SET stock_restored = 1 WHERE id = :id AND stock_restored = 0"),
        {"id": order.id},
    )
    if claimed.rowcount != 1:
        return  # 已被回补过(抢占失败)
    details = list((await db.execute(
        select(OrderDetail).where(OrderDetail.order_id == order.id)
    )).scalars().all())
    for d in details:
        if d.dish_id is not None:
            # 仅在 MySQL 实际回补(有限量)时同步 Redis,避免不限量商品被误建库存 key
            r = await db.execute(
                text("UPDATE dish SET stock = stock + :n WHERE id = :id AND stock IS NOT NULL"),
                {"n": d.number, "id": d.dish_id},
            )
            if r.rowcount == 1:
                await _redis_incr_stock(f"{STOCK_DISH_PREFIX}{d.dish_id}", d.number)
        elif d.setmeal_id is not None:
            r = await db.execute(
                text("UPDATE setmeal SET stock = stock + :n WHERE id = :id AND stock IS NOT NULL"),
                {"n": d.number, "id": d.setmeal_id},
            )
            if r.rowcount == 1:
                await _redis_incr_stock(f"{STOCK_SETMEAL_PREFIX}{d.setmeal_id}", d.number)


def _create_order_number(user_id: int) -> str:
    ts = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # yyyyMMddHHmmssSSS
    return f"{ts}{user_id}{random.randint(100, 999)}"


async def submit(db: AsyncSession, user_id: int, dto: OrdersSubmitIn) -> dict:
    # 0. 防重复提交:同用户并发下单串行化(锁粒度按用户;Redis 异常降级放行)
    lock_key, lock_id = f"lock:order:{user_id}", uuid.uuid4().hex
    locked = False
    try:
        try:
            locked = await redis_setnx(lock_key, lock_id, ORDER_LOCK_TTL)
        except Exception as e:
            logger.warning("下单防重锁降级(放行,Redis不可用): %s", e)
            locked = True  # 降级放行:不阻塞业务
        if not locked:
            raise BizException("操作过于频繁,请勿重复提交")

        return await _do_submit(db, user_id, dto)
    finally:
        if locked:
            await redis_release_lock(lock_key, lock_id)


async def _do_submit(db: AsyncSession, user_id: int, dto: OrdersSubmitIn) -> dict:
    # 0. 封禁拦截(纵深防御):正常路径下封禁已清 Redis 会话 → token 失效进不来,
    #    但 Redis 不可用时会话校验会降级放行,所以下单这条核心链路再查一次库兜底。
    user = await db.get(User, user_id)
    if user is None:
        raise BizException("用户不存在")
    if user.status == 0:
        raise BizException("账号已被封禁,无法下单")

    # 1. 校验地址
    address = (
        await db.execute(
            select(AddressBook).where(
                AddressBook.id == dto.address_book_id, AddressBook.user_id == user_id
            )
        )
    ).scalar_one_or_none()
    if address is None:
        raise BizException("地址不存在")

    # 2. 校验购物车非空
    cart_list = list((await db.execute(
        select(ShoppingCart).where(ShoppingCart.user_id == user_id)
    )).scalars().all())
    if not cart_list:
        raise BizException("购物车为空，无法下单")

    # 2.1 校验购物车商品仍在售(菜品/套餐起售且所属分类启用)
    for item in cart_list:
        if item.dish_id is not None:
            dish = await db.get(Dish, item.dish_id)
            if dish is None or dish.status != 1:
                raise BizException(f"菜品已下架: {item.name},请调整购物车")
            cat = await db.get(Category, dish.category_id)
            if cat is None or cat.status != 1:
                raise BizException(f"菜品所属分类已禁用: {item.name},请调整购物车")
        elif item.setmeal_id is not None:
            setmeal = await db.get(Setmeal, item.setmeal_id)
            if setmeal is None or setmeal.status != 1:
                raise BizException(f"套餐已下架: {item.name},请调整购物车")
            cat = await db.get(Category, setmeal.category_id)
            if cat is None or cat.status != 1:
                raise BizException(f"套餐所属分类已禁用: {item.name},请调整购物车")

    # 3. 配送距离校验(ak 未配置或调用失败则跳过)
    full_address = "".join(filter(None, [
        address.province_name, address.city_name, address.district_name, address.detail
    ]))
    distance = await get_distance(full_address)
    from app.core.config import LIMIT_DISTANCE
    if distance > LIMIT_DISTANCE:
        raise OrderStateException("下单失败，超出配送范围")

    # 4. 店铺营业中校验
    if await get_status(db) == 0:
        raise OrderStateException("下单失败，店铺不在营业中")

    # 4.1 下单预扣库存(不限量跳过;库存不足整单失败回滚)
    await _deduct_stock(db, cart_list)

    # 5. 组装订单
    order = Orders(
        user_id=user_id,
        address_book_id=dto.address_book_id,
        consignee=address.consignee,
        phone=address.phone,
        address=full_address,
        number=_create_order_number(user_id),
        order_time=datetime.now(),
        amount=sum((i.amount * i.number for i in cart_list), Decimal("0"))
        + Decimal(str(dto.pack_amount)) + Decimal(DELIVERY_FEE),
        pay_method=dto.pay_method,
        remark=dto.remark,
        status=1,
        pay_status=0,
        delivery_status=dto.delivery_status,
        estimated_delivery_time=_parse_dt(dto.estimated_delivery_time),
        pack_amount=dto.pack_amount,
        tableware_number=dto.tableware_number,
        tableware_status=dto.tableware_status,
    )
    db.add(order)
    await db.flush()

    # 6. 购物车 -> 订单明细
    for cart in cart_list:
        db.add(OrderDetail(
            order_id=order.id,
            name=cart.name,
            image=cart.image,
            dish_id=cart.dish_id,
            setmeal_id=cart.setmeal_id,
            dish_flavor=cart.dish_flavor,
            number=cart.number,
            amount=cart.amount,
        ))
    # 7. 清空购物车
    await db.execute(delete(ShoppingCart).where(ShoppingCart.user_id == user_id))
    await db.commit()

    return {
        "id": order.id,
        "orderNumber": order.number,
        "orderAmount": str(order.amount),
        "orderTime": order.order_time,
    }


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


async def payment(db: AsyncSession, user_id: int, order_number: str):
    """模拟支付:直接状态机流转 PAY(原项目无商户资质同此处理)"""
    order = (
        await db.execute(
            select(Orders).where(Orders.number == order_number, Orders.user_id == user_id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise OrderStateException("订单不存在")
    OrderStateMachine(order).pay()
    await db.commit()
    await _update_hot_sales(db, order, 1)  # 支付成功:热销榜销量 +N
    # WebSocket 推送新单提醒给管理端(type=1)
    await push_order_message(1, order.id, f"订单号: {order.number}")


async def history_orders(db: AsyncSession, user_id: int, page: int, page_size: int, status: Optional[int]) -> tuple[int, list]:
    """
    查询用户历史订单（分页）
    :param db: 异步数据库会话
    :param user_id: 当前登录用户ID，用于筛选该用户订单
    :param page: 当前页码，从1开始
    :param page_size: 每页展示条数
    :param status: 订单状态筛选条件，不传则查询全部状态订单
    :return: 元组(订单总条数, 当前页订单ORM对象列表)
    """
    # 初始化查询条件：固定只查询当前登录用户的订单
    conds = [Orders.user_id == user_id]

    # 如果前端传递了订单状态，则追加状态筛选条件
    if status is not None:
        conds.append(Orders.status == status)

    # 查询符合条件的订单总数量，无数据时默认0
    total = (await db.scalar(select(func.count(Orders.id)).where(*conds))) or 0

    # 分页查询订单数据
    result = await db.execute(
        select(Orders)
        .where(*conds)                      # 拼接所有筛选条件
        .order_by(Orders.order_time.desc()) # 按下单时间倒序，最新订单在前
        .offset((page - 1) * page_size)     # 分页偏移量，跳过前面页码数据
        .limit(page_size)                   # 限制当前页查询条数
    )

    # 返回总条数 + 当前页订单列表
    return total, list(result.scalars().all())


async def get_user_order_detail(db: AsyncSession, user_id: int, order_id: int) -> Orders:
    order = (
        await db.execute(
            select(Orders).where(Orders.id == order_id, Orders.user_id == user_id)
        )
    ).scalar_one_or_none()
    if order is None:
        raise OrderStateException("订单不存在")
    return order


async def repeat_order(db: AsyncSession, user_id: int, order_id: int):
    details = list((await db.execute(
        select(OrderDetail).where(OrderDetail.order_id == order_id)
    )).scalars().all())
    if not details:
        raise OrderStateException("订单不存在")

    # 校验所有菜品/套餐仍在售
    dish_ids = [d.dish_id for d in details if d.dish_id is not None]
    setmeal_ids = [d.setmeal_id for d in details if d.setmeal_id is not None]
    selling_dish_ids = list((await db.execute(
        select(Dish.id).where(Dish.id.in_(dish_ids), Dish.status == 1)
    )).scalars().all()) if dish_ids else []
    selling_setmeal_ids = list((await db.execute(
        select(Setmeal.id).where(Setmeal.id.in_(setmeal_ids), Setmeal.status == 1)
    )).scalars().all()) if setmeal_ids else []
    if len(selling_dish_ids) != len(set(dish_ids)) or len(selling_setmeal_ids) != len(set(setmeal_ids)):
        raise OrderStateException("存在菜品或套餐下架，无法重新创建购物车")

    now = datetime.now()
    for d in details:
        db.add(ShoppingCart(
            name=d.name, image=d.image, user_id=user_id,
            dish_id=d.dish_id, setmeal_id=d.setmeal_id,
            dish_flavor=d.dish_flavor, number=d.number, amount=d.amount,
            create_time=now,
        ))
    await db.commit()


async def user_cancel(db: AsyncSession, user_id: int, order_id: int):
    order = await get_user_order_detail(db, user_id, order_id)
    was_paid = order.pay_status == 1  # 状态机前记录,流转后会改成 REFUND
    OrderStateMachine(order).user_cancel()
    await _restore_stock(db, order)  # 取消回补库存(幂等)
    if was_paid:
        await _update_hot_sales(db, order, -1)  # 已支付退款:热销榜销量 -N
    await db.commit()


async def remind(db: AsyncSession, user_id: int, order_id: int):
    order = await get_user_order_detail(db, user_id, order_id)
    if order.status != 2:
        raise OrderStateException("当前订单状态不支持催单")
    # WebSocket 推送催单提醒给管理端(type=2)
    await push_order_message(2, order.id, f"订单号: {order.number}")


# ===== 管理端 =====

async def get_order_by_id(db: AsyncSession, order_id: int) -> Orders:
    order = await db.get(Orders, order_id)
    if order is None:
        raise OrderStateException("订单不存在")
    return order


async def condition_search(db: AsyncSession, page: int, page_size: int, status: Optional[int],
                           number: Optional[str], phone: Optional[str],
                           begin_time: Optional[str], end_time: Optional[str]) -> tuple[int, list]:
    conds = []
    if status is not None:
        conds.append(Orders.status == status)
    if number:
        conds.append(Orders.number.like(f"%{number}%"))
    if phone:
        conds.append(Orders.phone.like(f"%{phone}%"))
    if begin_time:
        conds.append(Orders.order_time >= _parse_dt(begin_time))
    if end_time:
        conds.append(Orders.order_time <= _parse_dt(end_time))
    total = (await db.scalar(select(func.count(Orders.id)).where(*conds))) or 0
    result = await db.execute(
        select(Orders)
        .where(*conds)
        .order_by(Orders.order_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return total, list(result.scalars().all())


async def statistics(db: AsyncSession) -> dict:
    """全库 count status=2/3/4(与原实现一致,无日期过滤)"""
    to_be_confirmed = await db.scalar(select(func.count(Orders.id)).where(Orders.status == 2)) or 0
    confirmed = await db.scalar(select(func.count(Orders.id)).where(Orders.status == 3)) or 0
    delivery_in_progress = await db.scalar(select(func.count(Orders.id)).where(Orders.status == 4)) or 0
    return {
        "toBeConfirmed": to_be_confirmed,
        "confirmed": confirmed,
        "deliveryInProgress": delivery_in_progress,
    }


async def _push_status_change(order: Orders, status_text: str):
    """推送订单状态变更给下单用户(type=3,按用户定向)"""
    await push_order_message(3, order.id, f"订单号: {order.number} {status_text}",
                             target="user", user_id=order.user_id)


async def confirm(db: AsyncSession, order_id: int):
    order = await get_order_by_id(db, order_id)
    OrderStateMachine(order).confirm_order()
    await db.commit()
    await _push_status_change(order, "已接单")


async def rejection(db: AsyncSession, order_id: int, reason: str):
    order = await get_order_by_id(db, order_id)
    was_paid = order.pay_status == 1  # 状态机前记录,流转后会改成 REFUND
    OrderStateMachine(order).admin_cancel(reason, is_rejection=True)
    await _restore_stock(db, order)  # 拒单回补库存(幂等)
    if was_paid:
        await _update_hot_sales(db, order, -1)  # 已支付拒单:热销榜销量 -N
    await db.commit()
    await _push_status_change(order, "已取消")


async def admin_cancel(db: AsyncSession, order_id: int, reason: str):
    order = await get_order_by_id(db, order_id)
    was_paid = order.pay_status == 1  # 状态机前记录,流转后会改成 REFUND
    OrderStateMachine(order).admin_cancel(reason, is_rejection=False)
    await _restore_stock(db, order)  # 取消回补库存(幂等)
    if was_paid:
        await _update_hot_sales(db, order, -1)  # 已支付取消:热销榜销量 -N
    await db.commit()
    await _push_status_change(order, "已取消")


async def delivery(db: AsyncSession, order_id: int):
    order = await get_order_by_id(db, order_id)
    OrderStateMachine(order).delivery()
    await db.commit()
    await _push_status_change(order, "派送中")


async def complete(db: AsyncSession, order_id: int):
    order = await get_order_by_id(db, order_id)
    OrderStateMachine(order).complete()
    await db.commit()
    await _push_status_change(order, "已完成")


async def build_order_vo(db: AsyncSession, order: Orders) -> dict:
    details = list((await db.execute(
        select(OrderDetail).where(OrderDetail.order_id == order.id)
    )).scalars().all())
    order_dishes = "".join(f"{d.name}*{d.number};" for d in details)
    return {
        "id": order.id,
        "number": order.number,
        "status": order.status,
        "userId": order.user_id,
        "addressBookId": order.address_book_id,
        "orderTime": order.order_time,
        "checkoutTime": order.checkout_time,
        "payMethod": order.pay_method,
        "payStatus": order.pay_status,
        "amount": str(order.amount) if order.amount is not None else None,
        "remark": order.remark,
        "phone": order.phone,
        "address": order.address,
        "userName": order.user_name,
        "consignee": order.consignee,
        "cancelReason": order.cancel_reason,
        "rejectionReason": order.rejection_reason,
        "cancelTime": order.cancel_time,
        "estimatedDeliveryTime": order.estimated_delivery_time,
        "deliveryStatus": order.delivery_status,
        "deliveryTime": order.delivery_time,
        "packAmount": order.pack_amount,
        "tablewareNumber": order.tableware_number,
        "tablewareStatus": order.tableware_status,
        "orderDetailList": [
            {
                "id": d.id,
                "name": d.name,
                "image": d.image,
                "orderId": d.order_id,
                "dishId": d.dish_id,
                "setmealId": d.setmeal_id,
                "dishFlavor": d.dish_flavor,
                "number": d.number,
                "amount": str(d.amount) if d.amount is not None else None,
            }
            for d in details
        ],
        "orderDishes": order_dishes,
    }
