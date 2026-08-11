"""员工删除单元测试:删除成功 / 防删自己 / 防删内置管理员 / 删除不存在"""
import pytest

from app.core.exceptions import BizException
from app.services import employee_service


async def _create_emp(db, username="test_emp"):
    """创建员工(操作人=1),返回员工 id"""
    emp = await employee_service.save(db, 1, "测试", username, "13800000000", "1", "110101199001011234")
    return emp.id


async def test_delete_success(db):
    """删除员工后查不到(操作人2 删员工1,避免与自增id撞号)"""
    emp_id = await _create_emp(db, "test_del1")
    await employee_service.delete(db, 2, emp_id)
    with pytest.raises(BizException) as exc:
        await employee_service.get_by_id(db, emp_id)
    assert "不存在" in str(exc.value)


async def test_delete_self_rejected(db):
    """不能删除当前登录账号"""
    emp_id = await _create_emp(db, "test_del2")
    with pytest.raises(BizException) as exc:
        await employee_service.delete(db, emp_id, emp_id)
    assert "当前登录账号" in str(exc.value)


async def test_delete_admin_rejected(db):
    """不能删除内置管理员 admin(操作人2 删 admin,先触发管理员保护)"""
    emp_id = await _create_emp(db, "admin")
    with pytest.raises(BizException) as exc:
        await employee_service.delete(db, 2, emp_id)
    assert "内置管理员" in str(exc.value)


async def test_delete_not_found(db):
    """删除不存在的员工被拒"""
    with pytest.raises(BizException) as exc:
        await employee_service.delete(db, 1, 99999)
    assert "不存在" in str(exc.value)
