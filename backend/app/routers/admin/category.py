"""管理端:分类管理 /admin/category"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import page_result
from app.core.result import ok
from app.core.security import get_current_admin
from app.schemas.business import CategoryIn
from app.services import category_service
from app.utils.orm import to_camel_dict

router = APIRouter(prefix="/admin/category", tags=["分类管理"])


@router.post("")
async def add(body: CategoryIn, db: AsyncSession = Depends(get_db), emp_id: int = Depends(get_current_admin)):
    """
    新增分类

    参数:
    - body (CategoryIn): 分类参数模型,包含 type 分类类型、name 名称、sort 排序。

    返回:
    - Result: 新增成功(create_user 记录当前操作人)。
    """
    await category_service.add(db, emp_id, body.type, body.name, body.sort)
    return ok()


@router.put("")
async def update(body: CategoryIn, db: AsyncSession = Depends(get_db), emp_id: int = Depends(get_current_admin)):
    """
    修改分类

    参数:
    - body (CategoryIn): 分类参数模型,包含 id 分类id及需要修改的字段。

    返回:
    - Result: 修改成功(update_user 记录当前操作人)。
    """
    await category_service.update(db, emp_id, body.id, body.type, body.name, body.sort)
    return ok()


@router.delete("", dependencies=[Depends(get_current_admin)])
async def delete(id: int = Query(...), db: AsyncSession = Depends(get_db)):
    """
    根据id删除分类

    参数:
    - id (int): 分类id。

    返回:
    - Result: 删除成功。
    """
    await category_service.delete(db, id)
    return ok()


@router.get("/page", dependencies=[Depends(get_current_admin)])
async def page(name: Optional[str] = None, type: Optional[int] = None,
               page: int = Query(1), pageSize: int = Query(10, alias="pageSize"),
               db: AsyncSession = Depends(get_db)):
    """
    分类分页查询

    参数:
    - name (str, 可选): 分类名称关键字,模糊查询。
    - type (int, 可选): 分类类型,1菜品分类 2套餐分类。
    - page (int): 页码,默认1。
    - pageSize (int): 每页条数,默认10。
    - db (Session): 数据库会话。

    返回:
    - Result: 分页结果 {total, records}。
    """
    total, rows = await category_service.page_query(db, name, type, page, pageSize)
    return ok(page_result(total, [to_camel_dict(r) for r in rows]))


@router.get("/list", dependencies=[Depends(get_current_admin)])
async def list_by_type(type: Optional[int] = None, db: AsyncSession = Depends(get_db)):
    """
    根据类型查询分类

    参数:
    - type (int, 可选): 分类类型,1菜品分类 2套餐分类。

    返回:
    - Result: 分类列表。
    """
    return ok([to_camel_dict(r) for r in await category_service.list_by_type(db, type)])


@router.post("/status/{status}")
async def change_status(status: int, id: int = Query(...), db: AsyncSession = Depends(get_db),
                        emp_id: int = Depends(get_current_admin)):
    """
    启用、禁用分类

    参数:
    - status (int): 目标状态,1启用 0禁用。
    - id (int): 分类id。

    返回:
    - Result: 操作成功(update_user 记录当前操作人)。
    """
    await category_service.change_status(db, emp_id, id, status)
    return ok()
