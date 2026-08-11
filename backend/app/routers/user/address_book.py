"""C端:地址簿 /user/addressBook"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.schemas.business import AddressBookIn, SetDefaultIn
from app.services import address_service
from app.utils.orm import to_camel_dict

router = APIRouter(prefix="/user/addressBook", tags=["C端-地址簿"])


def _data(body: AddressBookIn) -> dict:
    """将请求模型转换为服务层字典"""
    return {
        "consignee": body.consignee,
        "sex": body.sex,
        "phone": body.phone,
        "province_code": body.province_code,
        "province_name": body.province_name,
        "city_code": body.city_code,
        "city_name": body.city_name,
        "district_code": body.district_code,
        "district_name": body.district_name,
        "detail": body.detail,
        "label": body.label,
        "is_default": body.is_default,
    }


@router.post("")
async def save(body: AddressBookIn, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    新增地址

    参数:
    - body (AddressBookIn): 地址参数模型,包含 consignee 收货人、sex 性别、phone 手机号、detail 详细地址等。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 新增成功。
    """
    await address_service.save(db, user_id, _data(body))
    return ok()


@router.put("")
async def update(body: AddressBookIn, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    根据id修改地址

    参数:
    - body (AddressBookIn): 地址参数模型,包含 id 地址id及需要修改的字段。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 修改成功。
    """
    await address_service.update(db, user_id, body.id, _data(body))
    return ok()


@router.delete("")
async def delete(id: int = Query(...), db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    根据id删除地址

    参数:
    - id (int): 地址id。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 删除成功。
    """
    await address_service.delete(db, user_id, id)
    return ok()


@router.get("/list")
async def list_all(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    查询当前登录用户的所有地址信息

    参数:
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 地址列表。
    """
    return ok([to_camel_dict(a) for a in await address_service.list_all(db, user_id)])


@router.get("/default")
async def get_default(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    查询默认地址

    参数:
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 默认地址信息(无默认地址时返回 null)。
    """
    addr = await address_service.get_default(db, user_id)
    return ok(to_camel_dict(addr) if addr else None)


@router.put("/default")
async def set_default(body: SetDefaultIn, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    设置默认地址

    参数:
    - body (SetDefaultIn): 设置默认地址参数模型,包含 id 地址id。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 操作成功(原默认地址自动取消)。
    """
    await address_service.set_default(db, user_id, body.id)
    return ok()


@router.get("/{addr_id}")
async def get_by_id(addr_id: int, db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    根据id查询地址

    参数:
    - addr_id (int): 地址id。
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: 地址信息。
    """
    return ok(to_camel_dict(await address_service.get_by_id(db, user_id, addr_id)))
