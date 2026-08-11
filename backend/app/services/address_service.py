"""地址簿(文案与原 AddressServiceImpl 一致)"""
from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy import update as sql_update  # 别名:避免与本文件 update() 服务函数重名遮蔽
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_guard import validate_phone
from app.core.exceptions import BizException
from app.models import AddressBook


async def save(db: AsyncSession, user_id: int, data: dict) -> AddressBook:
    validate_phone(data.get("phone", ""))  # 手机号格式校验(数据库 varchar(11))
    # 若新增的地址设为默认,需先清除其他地址的默认标记(与原实现 updateIsDefaultByUserId 一致)
    if data.get("is_default") == 1:
        await db.execute(
            sql_update(AddressBook)
            .where(AddressBook.user_id == user_id, AddressBook.is_default == 1)
            .values(is_default=0)
        )
    addr = AddressBook(user_id=user_id, **data)
    db.add(addr)
    await db.commit()
    return addr


async def list_all(db: AsyncSession, user_id: int) -> list:
    result = await db.execute(
        select(AddressBook).where(AddressBook.user_id == user_id)
    )
    return list(result.scalars().all())


async def get_by_id(db: AsyncSession, user_id: int, addr_id: int) -> AddressBook:
    addr = (
        await db.execute(
            select(AddressBook).where(AddressBook.id == addr_id, AddressBook.user_id == user_id)
        )
    ).scalar_one_or_none()
    if addr is None:
        raise BizException("地址不存在")
    return addr


async def get_default(db: AsyncSession, user_id: int) -> Optional[AddressBook]:
    return (
        await db.execute(
            select(AddressBook).where(AddressBook.user_id == user_id, AddressBook.is_default == 1)
        )
    ).scalar_one_or_none()


async def set_default(db: AsyncSession, user_id: int, addr_id: int):
    addr = await get_by_id(db, user_id, addr_id)
    default = await get_default(db, user_id)
    if default is not None and default.id != addr_id:
        default.is_default = 0
    addr.is_default = 1
    await db.commit()


async def delete(db: AsyncSession, user_id: int, addr_id: int):
    await db.execute(
        delete(AddressBook).where(AddressBook.id == addr_id, AddressBook.user_id == user_id)
    )
    await db.commit()


async def update(db: AsyncSession, user_id: int, addr_id: int, data: dict):
    validate_phone(data.get("phone", ""))  # 手机号格式校验(数据库 varchar(11))
    addr = await get_by_id(db, user_id, addr_id)
    for k, v in data.items():
        setattr(addr, k, v)
    # 若编辑时设为默认,需先清除其他地址的默认标记(避免多个默认地址并存)
    if data.get("is_default") == 1:
        await db.execute(
            sql_update(AddressBook)
            .where(
                AddressBook.user_id == user_id,
                AddressBook.id != addr_id,
                AddressBook.is_default == 1,
            )
            .values(is_default=0)
        )
    await db.commit()
    return addr
