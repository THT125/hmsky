"""员工新增密码单元测试:初始密码设置 / 默认密码兜底 / 弱密码被拒"""
import pytest

from app.core.exceptions import BizException
from app.services import employee_service
from app.utils.password import verify_password


async def test_save_with_password(db):
    """管理员设置初始密码:bcrypt 存储,直接可登录,不强制改密"""
    emp = await employee_service.save(db, 1, "张三", "emp_pwd1", "13800000000", "1",
                                       "110101199001011234", "Admin@12345")
    assert verify_password("Admin@12345", emp.password) is True
    assert emp.force_change_password == 0


async def test_save_default_password(db):
    """不填密码:默认 123456 兜底,强制首次登录改密"""
    emp = await employee_service.save(db, 1, "李四", "emp_pwd2", "13800000001", "1",
                                       "110101199001011234")
    assert verify_password("123456", emp.password) is True
    assert emp.force_change_password == 1


async def test_save_weak_password_rejected(db):
    """初始密码强度不足被拒(仅字母/仅数字/过短)"""
    for weak in ["abcdefgh", "12345678", "a1"]:
        with pytest.raises(BizException):
            await employee_service.save(db, 1, "王五", f"emp_weak{len(weak)}", "13800000002", "1",
                                        "110101199001011234", weak)
