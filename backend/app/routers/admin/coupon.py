"""管理端:优惠券管理 /admin/coupon"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import page_result
from app.core.result import ok
from app.core.security import get_current_admin
from app.schemas.business import CouponIn
from app.services import coupon_service
from app.utils.orm import to_camel_dict

router = APIRouter(prefix="/admin/coupon", tags=["优惠券管理"])


@router.post("")
async def create(body: CouponIn, db: AsyncSession = Depends(get_db),
                emp_id: int = Depends(get_current_admin)):
    """
    新增优惠券模板(剩余量=发放总量,预热 Redis 存量)

    参数:
    - body (CouponIn): 券模板参数,包含 name/type/amount/minAmount/total/perUserLimit/startTime/endTime。
    """
    coupon_create=await coupon_service.create(db, emp_id, body)
    return ok(coupon_create)


@router.put("")
async def update(body: CouponIn, db: AsyncSession = Depends(get_db),
                emp_id: int = Depends(get_current_admin)):
    """
    编辑优惠券模板(stock 可传,补货场景;不传保持原剩余)

    参数:
    - body (CouponIn): 券模板参数,包含 id 及需要修改的字段。
    """
    coupon_update=await coupon_service.update(db, emp_id, body.id, body)
    return ok(coupon_update)


@router.get("/page", dependencies=[Depends(get_current_admin)])
async def page(name: Optional[str] = None, status: Optional[int] = None,
               page: int = Query(1), pageSize: int = Query(10, alias="pageSize"),
               db: AsyncSession = Depends(get_db)):
    """
    分页查询优惠券

    参数:
    - name (str, 可选): 券名称模糊查询。
    - status (int, 可选): 0停用 1启用。
    """
    total, rows = await coupon_service.page_query(db, name, status, page, pageSize)
    return ok(page_result(total, [to_camel_dict(r) for r in rows]))


@router.post("/status/{status}")
async def change_status(status: int, id: int = Query(...), db: AsyncSession = Depends(get_db),
                        emp_id: int = Depends(get_current_admin)):
    """
    上架/下架优惠券(下架停止发放,已领取的券不受影响)

    参数:
    - status (int): 0停用 1启用。
    - id (int): 券id。
    """
    await coupon_service.change_status(db, emp_id, id, status)
    return ok()


@router.delete("", dependencies=[Depends(get_current_admin)])
async def delete(ids: str = Query(...), db: AsyncSession = Depends(get_db)):
    """
    删除优惠券(已有用户领取的券禁止删除,只能下架)

    参数:
    - ids (str): 券id集合,逗号分隔。
    """
    id_list = [int(x) for x in ids.split(",") if x.strip()]
    await coupon_service.delete_by_ids(db, id_list)
    return ok()
