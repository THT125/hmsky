"""管理端:菜品管理 /admin/dish"""
from typing import List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import page_result
from app.core.result import ok
from app.core.security import get_current_admin
from app.models import Dish                    #菜品
from app.schemas.business import DishIn
from app.services import dish_service

router = APIRouter(prefix="/admin/dish", tags=["菜品管理"])


@router.post("")
async def save(body: DishIn, db: AsyncSession = Depends(get_db), emp_id: int = Depends(get_current_admin)):
    """
    新增菜品

    参数:
    - body (DishIn): 菜品参数模型,包含 name 名称、categoryId 分类id、price 价格、image 图片、description 描述、status 状态、flavors 口味列表。

    返回:
    - Result: 新增成功(create_user 记录当前操作人)。
    """
    await dish_service.save(db, emp_id, body.name, body.category_id, body.price, body.image,
                            body.description, body.status, body.flavors)
    return ok()


@router.put("")
async def update(body: DishIn, db: AsyncSession = Depends(get_db), emp_id: int = Depends(get_current_admin)):
    """
    修改菜品

    参数:
    - body (DishIn): 菜品参数模型,包含 id 菜品id及需要修改的字段。

    返回:
    - Result: 修改成功(update_user 记录当前操作人)。
    """
    await dish_service.update(db, emp_id, body.id, body.name, body.category_id, body.price,
                              body.image, body.description, body.status, body.flavors)
    return ok()


@router.delete("", dependencies=[Depends(get_current_admin)])
async def delete(ids: str = Query(...), db: AsyncSession = Depends(get_db)):
    """
    批量删除菜品

    参数:
    - ids (str): 菜品id集合,逗号分隔。
    - db (Session): 数据库会话。

    返回:
    - Result: 删除成功。
    """
    id_list: List[int] = [int(i) for i in ids.split(",") if i.strip()]
    await dish_service.delete_by_ids(db, id_list)
    return ok()


@router.get("/page", dependencies=[Depends(get_current_admin)])
async def page(name: Optional[str] = None, categoryId: Optional[int] = Query(None, alias="categoryId"),
               status: Optional[int] = None, page: int = Query(1), pageSize: int = Query(10, alias="pageSize"),
               db: AsyncSession = Depends(get_db)):
    """
    菜品分页查询

    参数:
    - name (str, 可选): 菜品名称关键字,模糊查询。
    - categoryId (int, 可选): 分类id。
    - status (int, 可选): 售卖状态,1起售 0停售。
    - page (int): 页码,默认1。
    - pageSize (int): 每页条数,默认10。
    - db (Session): 数据库会话。

    返回:
    - Result: 分页结果 {total, records},每条含 categoryName、flavors。
    """
    total, rows = await dish_service.page_query(db, name, categoryId, status, page, pageSize)
    return ok(page_result(total, [await dish_service.build_vo(db, d) for d in rows]))


@router.get("/list", dependencies=[Depends(get_current_admin)])
async def list_by_category(categoryId: Optional[str] = Query(None, alias="categoryId"),
                           db: AsyncSession = Depends(get_db)):
    """
    根据分类id查询菜品

    参数:
    - categoryId (str, 可选): 分类id;为空时返回全部菜品。

    返回:
    - Result: 菜品列表(含口味)。
    """
    # 前端可能传空字符串 ''，与 None 等价：返回全部菜品
    if categoryId not in (None, ""):
        return ok(await dish_service.list_by_category(db, int(categoryId)))
    dishes = list((await db.execute(select(Dish).order_by(Dish.create_time.asc()))).scalars().all())
    return ok([await dish_service.build_vo(db, d) for d in dishes])


@router.get("/{dish_id}", dependencies=[Depends(get_current_admin)])
async def get_by_id(dish_id: int, db: AsyncSession = Depends(get_db)):
    """
    根据id查询菜品

    参数:
    - dish_id (int): 菜品id。

    返回:
    - Result: 菜品信息,含 categoryName、flavors。
    """
    dish = await dish_service.get_by_id(db, dish_id)
    return ok(await dish_service.build_vo(db, dish))


@router.post("/status/{status}")
async def change_status(status: int, id: int = Query(...), db: AsyncSession = Depends(get_db),
                        emp_id: int = Depends(get_current_admin)):
    """
    菜品起售、停售

    参数:
    - status (int): 目标状态,1起售 0停售。
    - id (int): 菜品id。

    返回:
    - Result: 操作成功(update_user 记录当前操作人)。
    """
    await dish_service.change_status(db, emp_id, id, status)
    return ok()
