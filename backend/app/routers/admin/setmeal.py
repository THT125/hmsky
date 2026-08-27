"""管理端:套餐管理 /admin/setmeal"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import page_result
from app.core.result import ok
from app.core.security import get_current_admin
from app.schemas.business import SetmealIn
from app.services import setmeal_service

router = APIRouter(prefix="/admin/setmeal", tags=["套餐管理"])


@router.post("")
async def save(
    body: SetmealIn,
    db: AsyncSession = Depends(get_db),
    emp_id: int = Depends(get_current_admin)):
    """
    新增套餐

    参数:
    - body (SetmealIn): 套餐参数模型,包含 name 名称、categoryId 分类id、price 价格、image 图片、description 描述、status 状态、stock 库存(空=不限量)、setmealDishes 套餐菜品列表。

    返回:
    - Result: 新增成功(create_user 记录当前操作人)。
    """
    await setmeal_service.save(db, emp_id, body.category_id, body.name, body.price, body.image,
                               body.description, body.status, body.setmeal_dishes, body.stock)
    return ok()


@router.put("")
async def update(
    body: SetmealIn,
    db: AsyncSession = Depends(get_db),
    emp_id: int = Depends(get_current_admin)):
    """
    修改套餐

    参数:
    - body (SetmealIn): 套餐参数模型,包含 id 套餐id及需要修改的字段(含 stock 库存,空=不限量)。

    返回:
    - Result: 修改成功(update_user 记录当前操作人)。
    """
    await setmeal_service.update(db, emp_id, body.id, body.category_id, body.name, body.price,
                                 body.image, body.description, body.status, body.setmeal_dishes, body.stock)
    return ok()


@router.delete("", dependencies=[Depends(get_current_admin)])
async def delete(ids: str = Query(...), db: AsyncSession = Depends(get_db)):
    """
    批量删除套餐

    参数:
    - ids (str): 套餐id集合,逗号分隔。
    - db (Session): 数据库会话。

    返回:
    - Result: 删除成功(起售中的套餐会被跳过)。
    """
    id_list: List[int] = [int(i) for i in ids.split(",") if i.strip()]
    await setmeal_service.delete_by_ids(db, id_list)
    return ok()


@router.get("/page", dependencies=[Depends(get_current_admin)])
async def page(name: Optional[str] = None, categoryId: Optional[int] = Query(None, alias="categoryId"),
               status: Optional[int] = None, page: int = Query(1), pageSize: int = Query(10, alias="pageSize"),
               db: AsyncSession = Depends(get_db)):
    """
    套餐分页查询

    参数:
    - name (str, 可选): 套餐名称关键字,模糊查询。
    - categoryId (int, 可选): 分类id。
    - status (int, 可选): 售卖状态,1起售 0停售。
    - page (int): 页码,默认1。
    - pageSize (int): 每页条数,默认10。
    - db (Session): 数据库会话。

    返回:
    - Result: 分页结果 {total, records},每条含 categoryName、setmealDishes。
    """
    total, rows = await setmeal_service.page_query(db, name, categoryId, status, page, pageSize)
    return ok(page_result(total, [await setmeal_service.build_vo(db, s) for s in rows]))


@router.get("/{setmeal_id}", dependencies=[Depends(get_current_admin)])
async def get_by_id(setmeal_id: int, db: AsyncSession = Depends(get_db)):
    """
    根据id查询套餐

    参数:
    - setmeal_id (int): 套餐id。

    返回:
    - Result: 套餐信息,含 categoryName、setmealDishes。
    """
    setmeal = await setmeal_service.get_by_id(db, setmeal_id)
    return ok(await setmeal_service.build_vo(db, setmeal))


@router.post("/status/{status}")
async def change_status(status: int, id: int = Query(...), db: AsyncSession = Depends(get_db),
                        emp_id: int = Depends(get_current_admin)):
    """
    套餐起售、停售

    参数:
    - status (int): 目标状态,1起售 0停售。
    - id (int): 套餐id。

    返回:
    - Result: 操作成功(update_user 记录当前操作人)。
    """
    await setmeal_service.change_status(db, emp_id, id, status)
    return ok()
