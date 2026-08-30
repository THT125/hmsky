"""C端:优惠券(领券中心/抢券/我的券)/user/coupon"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.services import coupon_service

router = APIRouter(prefix="/user/coupon", tags=["C端-优惠券"])


@router.get("/list", dependencies=[Depends(get_current_user)])
async def list_coupons(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    领券中心列表:上架券 + 实时库存 + 用户领取状态

    返回:
    - Result: [{id, name, type, amount, minAmount, stock, perUserLimit, startTime, endTime, grabStatus}]
      grabStatus: available可领取 / grabbed已领取 / sold_out已抢完 / not_started未开始 / ended已结束
    """
    coupon_list=await coupon_service.list_for_user(db, user_id)
    return ok(coupon_list)


@router.post("/grab/{coupon_id}", dependencies=[Depends(get_current_user)])
async def grab(coupon_id: int, db: AsyncSession = Depends(get_db),
               user_id: int = Depends(get_current_user)):
    """
    抢券:Redis 闸门三层防超发(限领 SETNX → Lua 原子扣减 → MySQL 唯一约束兜底)

    参数:
    - coupon_id (int): 券id。
    """
    coupon_grab=await coupon_service.grab(db, user_id, coupon_id)
    return ok(coupon_grab)


@router.get("/my", dependencies=[Depends(get_current_user)])
async def my_coupons(status: Optional[int] = Query(None), db: AsyncSession = Depends(get_db),
                     user_id: int = Depends(get_current_user)):
    """
    我的优惠券

    参数:
    - status (int, 可选): 0未用 1已用 2已过期;不传查全部。

    返回:
    - Result: [{id, couponId, name, type, amount, minAmount, status, createTime}]
    """
    my_coupons=await coupon_service.my_coupons(db, user_id, status)
    return ok(my_coupons)
