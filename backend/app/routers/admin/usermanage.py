"""管理端:用户管理 /admin/user

⚠️ 路由注册顺序有讲究:字面量路径(/page、/risk、/export、/grantCoupon、/status)
必须排在 /{user_id} 之前 —— FastAPI 按注册顺序匹配,否则 /export 会被当作 user_id
解析成 int 而报 422。
"""
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Optional
from urllib.parse import quote

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import page_result
from app.core.result import ok
from app.core.security import get_current_admin
from app.schemas.business import UserGrantCouponIn
from app.services import risk_service
from app.services import user_admin_service as svc
from app.utils import ip_region
from app.utils.orm import to_camel_dict

router = APIRouter(prefix="/admin/user", tags=["用户管理"])


@router.get("/page", dependencies=[Depends(get_current_admin)])
async def page(
    username: Optional[str] = None,
    phone: Optional[str] = None,
    status: Optional[int] = None,
    begin: Optional[date] = None,
    end: Optional[date] = None,
    min_amount: Optional[Decimal] = Query(None, alias="minAmount"),
    max_amount: Optional[Decimal] = Query(None, alias="maxAmount"),
    page: int = Query(1),
    page_size: int = Query(10, alias="pageSize"),
    db: AsyncSession = Depends(get_db),
):
    """
    用户分页查询

    参数:
    - username (str, 可选): 用户名关键字,模糊查询。
    - phone (str, 可选): 手机号关键字,模糊查询。
    - status (int, 可选): 账号状态 1正常 0封禁。
    - begin / end (date, 可选): 注册时间范围 yyyy-MM-dd。
    - minAmount / maxAmount (Decimal, 可选): 累计消费额范围(已完成订单金额之和),用于用户分群。
    - page / pageSize (int): 分页参数。

    返回:
    - Result: {total, records}。records 中**不含 password 字段**。
    """
    total, rows = await svc.page_query(
        db, username=username, phone=phone, status=status, begin=begin, end=end,
        min_amount=min_amount, max_amount=max_amount, page=page, page_size=page_size)
    # 累计消费:一次 IN 查询补齐整页(避免 N+1);列表要展示,也是分群筛选的依据
    spends = await svc.spend_map(db, [u.id for u in rows])
    records = []
    for u in rows:
        # ⚠️ 必须排除 password:员工分页接口曾因漏排除把 bcrypt 哈希返回给前端
        d = to_camel_dict(u, exclude=("password",))
        d["totalSpend"] = float(spends.get(u.id, 0))
        records.append(d)
    return ok(page_result(total, records))


@router.get("/risk", dependencies=[Depends(get_current_admin)])
async def risk(days: int = Query(7), limit: int = Query(100), db: AsyncSession = Depends(get_db)):
    """
    风险用户列表(风控)

    基于登录日志实时分析三类异常:多 IP 登录 / 同 IP 多账号(撞库)/ 高频登录失败。

    参数:
    - days (int): 统计窗口天数,默认 7。
    - limit (int): 最多返回条数,默认 100。

    返回:
    - Result: 风险用户列表 [{userId, username, phone, riskLevel, signals, ips, ...}]。
    """
    return ok(await risk_service.risk_users(db, days=days, limit=limit))


@router.get("/export", dependencies=[Depends(get_current_admin)])
async def export(
    username: Optional[str] = None,
    phone: Optional[str] = None,
    status: Optional[int] = None,
    begin: Optional[date] = None,
    end: Optional[date] = None,
    min_amount: Optional[Decimal] = Query(None, alias="minAmount"),
    max_amount: Optional[Decimal] = Query(None, alias="maxAmount"),
    db: AsyncSession = Depends(get_db),
):
    """
    导出用户列表 Excel

    筛选条件与分页接口完全一致(同口径),但**有条数上限**(见 EXPORT_LIMIT)。

    返回:
    - StreamingResponse: xlsx 文件流。
    """
    content, filename = await svc.build_export_excel(
        db, username=username, phone=phone, status=status, begin=begin, end=end,
        min_amount=min_amount, max_amount=max_amount)
    return StreamingResponse(
        BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )


@router.post("/grantCoupon")
async def grant_coupon(body: UserGrantCouponIn, db: AsyncSession = Depends(get_db),
                       emp_id: int = Depends(get_current_admin)):
    """
    批量发券(运营)

    给选中的用户发放同一张优惠券。与用户"抢券"不同,后台发券不走 Redis 闸门,
    但库存扣减仍走 MySQL 条件更新防超发 —— 可能与用户抢券同时发生。

    参数:
    - body (UserGrantCouponIn): couponId 券模板id、userIds 目标用户id列表。

    返回:
    - Result: {granted 实际发放数, skipped 跳过数(已领过), stockLeft 剩余库存}。
    库存不足时**整批拒绝**,不做部分发放。
    """
    return ok(await svc.grant_coupon(db, emp_id, body.coupon_id, body.user_ids))


@router.post("/status/{status}")
async def change_status(status: int, id: int = Query(...), reason: Optional[str] = Query(None),
                        db: AsyncSession = Depends(get_db),
                        emp_id: int = Depends(get_current_admin)):
    """
    封禁 / 解封用户

    封禁 = 禁登录 + 即时踢下线(清 Redis 会话)+ 记录封禁原因;
    下单接口另有纵深拦截,防 Redis 不可用时会话校验降级放行。

    参数:
    - status (int): 目标状态 1正常 0封禁。
    - id (int): 用户id。
    - reason (str, 可选): 封禁原因(审计用,解封时自动清空)。

    返回:
    - Result: 操作成功。不做物理删除(订单/优惠券有关联)。
    """
    await svc.change_status(db, emp_id, id, status, reason)
    return ok()


@router.get("/{user_id}/loginLogs", dependencies=[Depends(get_current_admin)])
async def login_logs(user_id: int, page: int = Query(1),
                     page_size: int = Query(10, alias="pageSize"),
                     db: AsyncSession = Depends(get_db)):
    """
    用户登录日志分页

    登录日志表一直在写,这个接口补上"读"的那一半。

    参数:
    - user_id (int): 用户id。
    - page / pageSize (int): 分页参数。

    返回:
    - Result: {total, records},含登录方式/成功失败/IP/UA/时间。
    """
    total, rows = await svc.login_logs(db, user_id, page, page_size)
    # 补 IP 归属地(离线库;失败降级为 None,IP 原样展示)
    regions = await ip_region.lookup_many([r.ip for r in rows])
    records = []
    for r in rows:
        d = to_camel_dict(r)
        d["region"] = regions.get(r.ip)
        records.append(d)
    return ok(page_result(total, records))


@router.get("/{user_id}", dependencies=[Depends(get_current_admin)])
async def get_detail(user_id: int, db: AsyncSession = Depends(get_db)):
    """
    用户详情

    参数:
    - user_id (int): 用户id。

    返回:
    - Result: 基本信息 + 统计(订单数/已完成数/累计消费)+ 最近 10 笔订单。不含 password。
    """
    result=await svc.get_detail(db, user_id)
    return ok(result)
