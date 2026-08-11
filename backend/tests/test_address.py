"""地址簿单元测试:默认地址唯一性 + 手机号校验"""
import pytest

from sqlalchemy import select

from app.core.exceptions import BizException
from app.models import AddressBook
from app.services import address_service


async def _seed(db, addr_id, consignee, is_default):
    db.add(AddressBook(id=addr_id, user_id=1, consignee=consignee, sex="1",
                       phone="13800000001", detail=f"地址{addr_id}", is_default=is_default))
    await db.commit()


async def test_set_default_clears_others(db):
    """设置默认地址时,其他地址的默认标记被清除"""
    await _seed(db, 1, "甲", 1)
    await _seed(db, 2, "乙", 0)
    await address_service.set_default(db, user_id=1, addr_id=2)
    rows = (await db.execute(select(AddressBook))).scalars().all()
    default_count = sum(1 for r in rows if r.is_default == 1)
    assert default_count == 1
    assert next(r for r in rows if r.id == 2).is_default == 1


async def test_update_with_default_clears_others(db):
    """编辑地址携带 isDefault=1 时,其他地址默认标记被清除(修复的 bug 场景)"""
    await _seed(db, 1, "甲", 1)
    await _seed(db, 2, "乙", 0)
    await address_service.update(db, user_id=1, addr_id=2, data={
        "consignee": "乙", "sex": "1", "phone": "13800000002", "detail": "地址2", "is_default": 1,
    })
    rows = (await db.execute(select(AddressBook))).scalars().all()
    default_count = sum(1 for r in rows if r.is_default == 1)
    assert default_count == 1
    assert next(r for r in rows if r.id == 2).is_default == 1


async def test_save_with_default_clears_others(db):
    """新增地址带 isDefault=1 时,其他地址默认标记被清除"""
    await _seed(db, 1, "甲", 1)
    await address_service.save(db, user_id=1, data={
        "consignee": "乙", "sex": "1", "phone": "13800000002", "detail": "地址2", "is_default": 1,
    })
    rows = (await db.execute(select(AddressBook))).scalars().all()
    default_count = sum(1 for r in rows if r.is_default == 1)
    assert default_count == 1
    assert next(r for r in rows if r.id != 1).is_default == 1


async def test_save_invalid_phone_rejected(db):
    """地址手机号格式非法被拒(与数据库 varchar(11) 一致)"""
    with pytest.raises(BizException) as exc:
        await address_service.save(db, user_id=1, data={
            "consignee": "甲", "sex": "1", "phone": "138000000001", "detail": "地址1",
        })
    assert "手机号" in str(exc.value)


async def test_get_default_returns_only_one(db):
    """get_default 返回唯一默认地址"""
    await _seed(db, 1, "甲", 1)
    await _seed(db, 2, "乙", 0)
    default = await address_service.get_default(db, user_id=1)
    assert default is not None
    assert default.id == 1
