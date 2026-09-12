"""管理端用户管理:查询 / 详情统计 / 封禁解封 / 登录日志。

设计要点:
- **不做物理删除** —— 订单、优惠券都有 user 关联,删用户会留下悬空外键。
  企业里用户账号只封禁不删除。
- **封禁 = 禁登录 + 即时踢下线 + 禁止下单**,三者缺一不可:
  只改数据库的话,JWT 还有最长 2 小时有效期,被禁用户照常下单。
- 详情统计用**一次条件聚合**拿全三个数字,避免 3 次 DB 往返。
"""
import logging
from datetime import date, datetime, timedelta
from decimal import Decimal
from io import BytesIO
from typing import List, Optional

from openpyxl import Workbook
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BizException
from app.core.redis import COUPON_STOCK_PREFIX
from app.core.security import SESSION_USER_PREFIX
from app.models import Coupon, Orders, User, UserCoupon, UserLoginLog
from app.utils.ip_region import lookup as lookup_region

logger = logging.getLogger("uvicorn.error")

# 有效订单口径:与全项目一致(status=5 已完成)
VALID_ORDER_STATUS = 5

# 导出条数上限:openpyxl 把整个工作簿放内存 + 是同步阻塞调用,无上限会 OOM/卡死事件循环
EXPORT_LIMIT = 10000


async def _clear_session(user_id: int):
    """清除会话:封禁即踢下线,该用户所有已签发 token 立即失效。

    照抄 user_service._clear_session 的降级模式:Redis 不可用只告警不抛错,
    因为"清会话失败"不应阻塞封禁本身(封禁落库 + 登录拦截仍然生效)。
    """
    try:
        from app.core.redis import redis_delete

        await redis_delete(f"{SESSION_USER_PREFIX}{user_id}")
    except Exception as e:
        logger.warning("清用户会话降级(Redis不可用,旧token可能暂未失效): %s", e)


async def _spend_subquery():
    """累计消费额的相关子查询(已完成订单金额之和)。

    用户没有已完成订单时返回 0(LEFT JOIN 语义),这样"消费额 < 10"也能筛出零消费用户。
    """
    result=(select(func.coalesce(func.sum(Orders.amount), 0))
        .where(Orders.user_id == User.id, Orders.status == VALID_ORDER_STATUS)
        .correlate(User)
        .scalar_subquery())
    return (result)


async def _build_conds(username: Optional[str], phone: Optional[str], status: Optional[int],
                       begin: Optional[date], end: Optional[date],
                       min_amount: Optional[Decimal], max_amount: Optional[Decimal]) -> list:
    """组装筛选条件(分页与导出共用,保证口径一致)"""
    conds = []
    if username:
        conds.append(User.username.like(f"%{username}%"))
    if phone:
        conds.append(User.phone.like(f"%{phone}%"))
    if status is not None:
        conds.append(User.status == status)
    if begin:
        conds.append(func.date(User.create_time) >= begin)
    if end:
        conds.append(func.date(User.create_time) <= end)
    # 消费额分群:>0 才有意义,等于 0 用 min_amount=0 表达
    if min_amount is not None or max_amount is not None:
        spend = await _spend_subquery()
        if min_amount is not None:
            conds.append(spend >= min_amount)
        if max_amount is not None:
            conds.append(spend <= max_amount)
    return conds


async def page_query(db: AsyncSession, username: Optional[str] = None, phone: Optional[str] = None,
                     status: Optional[int] = None, begin: Optional[date] = None,
                     end: Optional[date] = None, min_amount: Optional[Decimal] = None,
                     max_amount: Optional[Decimal] = None,
                     page: int = 1, page_size: int = 10) -> tuple[int, list]:
    """用户分页查询(支持用户名/手机号/状态/注册时间/累计消费额筛选)"""
    conds = await _build_conds(username, phone, status, begin, end, min_amount, max_amount)
    total = (await db.scalar(select(func.count(User.id)).where(*conds))) or 0
    rows = (
        await db.execute(
            select(User)
            .where(*conds)
            .order_by(User.create_time.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return total, list(rows)


async def spend_map(db: AsyncSession, user_ids: List[int]) -> dict:
    """批量取用户累计消费额(列表展示用)。

    用一次 IN 查询替代 N 次单查(避免 N+1),口径与详情页一致:只算已完成订单(status=5)。
    """
    if not user_ids:
        return {}
    rows = (await db.execute(
        select(Orders.user_id, func.coalesce(func.sum(Orders.amount), 0))
        .where(Orders.user_id.in_(user_ids), Orders.status == VALID_ORDER_STATUS)
        .group_by(Orders.user_id)
    )).all()
    return {r[0]: Decimal(str(r[1] or 0)) for r in rows}


async def export_rows(db: AsyncSession, limit: int,
                      username: Optional[str] = None, phone: Optional[str] = None,
                      status: Optional[int] = None, begin: Optional[date] = None,
                      end: Optional[date] = None, min_amount: Optional[Decimal] = None,
                      max_amount: Optional[Decimal] = None) -> list:
    """导出用查询:与分页同口径,但**必须带上限**。

    openpyxl 会把整个工作簿放在内存里,无上限导出在 2G 实例上会 OOM;
    而且它是同步阻塞调用,条数越多卡住事件循环越久。上限是这两件事的共同护栏。
    """
    conds = await _build_conds(username, phone, status, begin, end, min_amount, max_amount)
    spend = await _spend_subquery()
    rows = (
        await db.execute(
            select(
                User.id, User.username, User.phone, User.sex, User.status,
                User.create_time, User.last_login_time, User.last_login_ip,
                spend.label("total_spend"),
            )
            .where(*conds)
            .order_by(User.create_time.desc(), User.id.desc())
            .limit(limit)
        )
    ).all()
    return list(rows)


async def get_by_id(db: AsyncSession, user_id: int) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise BizException("用户不存在")
    return user


async def get_detail(db: AsyncSession, user_id: int) -> dict:
    """用户详情:基本信息 + 统计 + 最近订单

    统计用一次条件聚合拿全(全部订单数 / 已完成数 / 累计消费),
    避免为每个数字单独查一次库。
    """
    user = await get_by_id(db, user_id)

    stats = (
        await db.execute(
            select(
                func.count(Orders.id),
                func.coalesce(func.sum(case((Orders.status == VALID_ORDER_STATUS, 1), else_=0)), 0),
                func.coalesce(func.sum(case((Orders.status == VALID_ORDER_STATUS, Orders.amount), else_=0)), 0),
            ).where(Orders.user_id == user_id)
        )
    ).one()
    order_count, valid_order_count, total_spend = int(stats[0] or 0), int(stats[1] or 0), Decimal(str(stats[2] or 0))

    recent = (
        await db.execute(
            select(Orders)
            .where(Orders.user_id == user_id)
            .order_by(Orders.id.desc())
            .limit(10)
        )
    ).scalars().all()

    last_login_region = await lookup_region(user.last_login_ip)

    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "sex": user.sex,
        "avatar": user.avatar,
        "status": user.status,
        "banReason": user.ban_reason,
        "createTime": user.create_time,
        "lastLoginTime": user.last_login_time,
        "lastLoginIp": user.last_login_ip,
        "lastLoginRegion": last_login_region,
        "orderCount": order_count,
        "validOrderCount": valid_order_count,
        "totalSpend": total_spend,
        "recentOrders": [
            {
                "id": o.id, "number": o.number, "status": o.status,
                "amount": o.amount, "orderTime": o.order_time,
            }
            for o in recent
        ],
    }


async def change_status(db: AsyncSession, operator_id: int, user_id: int, status: int,
                        reason: Optional[str] = None):
    """封禁 / 解封用户。

    封禁动作包含三件事,缺一不可:
      ① status=0        → 登录接口拦截(见 user_service.login)
      ② 清 Redis 会话    → 已登录的 token 立即失效(否则 JWT 还能用满 2 小时)
      ③ 记录 ban_reason  → 审计:谁、为什么封的
    第 ③ 项同时也是下单接口纵深拦截的依据。
    """
    if status not in (0, 1):
        raise BizException("状态参数不正确")
    user = await get_by_id(db, user_id)

    if status == 0:
        user.ban_reason = (reason or "").strip() or None
        await _clear_session(user_id)  # 即时踢下线
    else:
        user.ban_reason = None

    user.status = status
    user.update_user = operator_id
    await db.commit()
    return user


async def login_logs(db: AsyncSession, user_id: int, page: int = 1, page_size: int = 10) -> tuple[int, list]:
    """登录日志分页(数据一直在写,这个接口是补上"读"的那一半)"""
    total = (await db.scalar(
        select(func.count(UserLoginLog.id)).where(UserLoginLog.user_id == user_id))) or 0
    rows = (
        await db.execute(
            select(UserLoginLog)
            .where(UserLoginLog.user_id == user_id)
            .order_by(UserLoginLog.create_time.desc(), UserLoginLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).scalars().all()
    return total, list(rows)


# ===== 运营:批量发券 =====

async def grant_coupon(db: AsyncSession, operator_id: int, coupon_id: int,
                       user_ids: List[int]) -> dict:
    """批量发券(运营能力)。

    与"抢券"的区别:后台发券**不走 Redis 闸门**,直接落库 —— 因为发券量可控、
    且运营需要"要么全发要么不发"的确定性,不适合走"手慢了"那套逐条竞争。

    但**防超发不能省**:后台发券可能和用户抢券同时发生,所以库存扣减仍用
    MySQL 条件更新(项目既有的兜底模式:`stock >= N` 不满足则 rowcount=0)。
    """
    if not user_ids:
        raise BizException("请先选择要发放的用户")
    # 去重:前端多选可能带重复 id,不去重会多发券
    targets = list(dict.fromkeys(user_ids))

    coupon = await db.get(Coupon, coupon_id)
    if coupon is None:
        raise BizException("优惠券不存在")
    if coupon.status != 1:
        raise BizException("优惠券已停用")
    now = datetime.now()
    if now > coupon.end_time:
        raise BizException("优惠券已过可领时间")

    # 先过滤已领过的:唯一约束能兜底,但让整批失败对运营不友好
    claimed = set((await db.execute(
        select(UserCoupon.user_id)
        .where(UserCoupon.coupon_id == coupon_id, UserCoupon.user_id.in_(targets))
    )).scalars().all())
    targets = [uid for uid in targets if uid not in claimed]
    if not targets:
        raise BizException("所选用户都已领取过该优惠券")

    # 原子扣减:库存不足则整批拒绝(不做部分发放,避免运营对不上账)
    r = await db.execute(
        text("UPDATE coupon SET stock = stock - :n WHERE id = :id AND stock >= :n"),
        {"n": len(targets), "id": coupon_id},
    )
    if r.rowcount != 1:
        # 先取库存值再 rollback —— rollback 会让 ORM 对象过期,
        # 之后访问 coupon.stock 会触发懒加载 IO(f"库存不足" 反而抛 MissingGreenlet)
        current_stock = coupon.stock
        await db.rollback()
        raise BizException(f"库存不足:需要 {len(targets)} 张,当前仅剩 {current_stock} 张")

    expire_time = now + timedelta(days=int(coupon.valid_days or 30))
    for uid in targets:
        db.add(UserCoupon(user_id=uid, coupon_id=coupon_id, status=0, expire_time=expire_time))
    await db.commit()

    # 同步 Redis 库存(MySQL 为权威):key 存在则同量递减,不存在则跳过 ——
    # 跳过是安全的:下次读取会从 DB 回填,且 DB 条件更新才是最终闸门。
    try:
        from app.core.redis import redis_decrby, redis_exists

        key = f"{COUPON_STOCK_PREFIX}{coupon_id}"
        if await redis_exists(key):
            await redis_decrby(key, len(targets))
    except Exception as e:
        logger.warning("发券同步Redis库存降级(MySQL仍为权威): %s", e)

    # 审计:user_coupon 表没有"发放人"字段(用户自己抢的券和后台发的券同表),
    # 所以发放行为记在日志里。若将来需要按发放人查询,再给该表加 granted_by 列。
    logger.info("管理员 %s 给 %d 个用户发放优惠券 %s(跳过已领 %d 人)",
                operator_id, len(targets), coupon_id, len(claimed))

    # 剩余库存重新查库:上面的 raw UPDATE 绕过了 ORM,内存里的 coupon.stock 已过期
    stock_left = await db.scalar(select(Coupon.stock).where(Coupon.id == coupon_id))
    return {"granted": len(targets), "skipped": len(claimed), "stockLeft": int(stock_left or 0)}


# ===== 运营:导出 =====

async def build_export_excel(db: AsyncSession, **filters) -> tuple[bytes, str]:
    """导出用户列表为 xlsx(动态生成,不套模板)。

    ⚠️ 条数上限见 EXPORT_LIMIT —— openpyxl 全量加载进内存且是同步阻塞调用,
    无上限在 2G 实例上会 OOM,同时卡住事件循环。
    """
    rows = await export_rows(db, EXPORT_LIMIT, **filters)

    wb = Workbook()
    ws = wb.active
    ws.title = "用户列表"
    ws.append(["ID", "用户名", "手机号", "性别", "状态",
               "注册时间", "最近登录", "最近登录IP", "累计消费(元)"])

    def _fmt(v):
        return v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, datetime) else (v if v is not None else "")

    for r in rows:
        ws.append([
            r[0], r[1], r[2],
            "男" if r[3] == "1" else ("女" if r[3] == "0" else ""),
            "正常" if r[4] == 1 else "封禁",
            _fmt(r[5]), _fmt(r[6]), r[7] or "",
            float(r[8] or 0),
        ])
    # 手机号列按文本处理,避免 Excel 当数字显示成科学计数法
    for cell in ws["C"][1:]:
        cell.number_format = "@"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue(), f"用户列表{date.today().isoformat()}.xlsx"
