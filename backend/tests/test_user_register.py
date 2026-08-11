"""用户注册单元测试:手机号必填/唯一、用户名唯一(验证码打桩)"""
import pytest

from app.core.exceptions import BizException
from app.services import user_service


async def _stub_captcha(monkeypatch):
    """打桩验证码校验(通过)"""
    async def fake_verify(uuid, code):
        pass
    monkeypatch.setattr(user_service, "verify_captcha", fake_verify)


async def test_register_success(db, monkeypatch):
    """注册成功:用户名+手机号+密码入库,自动登录"""
    await _stub_captcha(monkeypatch)
    data = await user_service.register(db, "zhangsan", "abc12345", "13800138000")
    assert data["username"] == "zhangsan"
    assert data["token"]
    from sqlalchemy import select
    from app.models import User
    user = (await db.execute(select(User).where(User.username == "zhangsan"))).scalar_one()
    assert user.phone == "13800138000"
    assert user.password.startswith("$2")  # bcrypt


async def test_register_duplicate_username(db, monkeypatch):
    """用户名重复被拒"""
    await _stub_captcha(monkeypatch)
    await user_service.register(db, "zhangsan", "abc12345", "13800138000")
    with pytest.raises(BizException) as exc:
        await user_service.register(db, "zhangsan", "abc12345", "13900139000")
    assert "用户名" in str(exc.value)


async def test_register_duplicate_phone(db, monkeypatch):
    """手机号重复被拒(防一机多号/撞号)"""
    await _stub_captcha(monkeypatch)
    await user_service.register(db, "zhangsan", "abc12345", "13800138000")
    with pytest.raises(BizException) as exc:
        await user_service.register(db, "lisi", "abc12345", "13800138000")
    assert "手机号" in str(exc.value)


async def test_register_invalid_phone(db, monkeypatch):
    """手机号格式非法被拒"""
    await _stub_captcha(monkeypatch)
    with pytest.raises(BizException) as exc:
        await user_service.register(db, "zhangsan", "abc12345", "12345")
    assert "手机号" in str(exc.value)


# ===== 个人资料 =====

async def test_profile_roundtrip(db, monkeypatch):
    """资料读写:更新后能读回,用户名/手机号不可改"""
    await _stub_captcha(monkeypatch)
    reg = await user_service.register(db, "zhangsan", "abc12345", "13800138000")
    uid = reg["id"]

    # 修改资料
    updated = await user_service.update_profile(db, uid, {
        "sex": "1", "avatar": "/static/a.png",
    })
    assert updated["sex"] == "1"
    assert updated["avatar"] == "/static/a.png"
    assert updated["username"] == "zhangsan"  # 用户名不可改
    assert updated["phone"] == "13800138000"  # 手机号不可改
    assert "name" not in updated  # name 字段已删除
    assert "idNumber" not in updated  # 身份证字段已删除

    # 读回一致
    profile = await user_service.get_profile(db, uid)
    assert profile["sex"] == "1"


async def test_profile_invalid_sex(db, monkeypatch):
    """性别参数非法被拒"""
    await _stub_captcha(monkeypatch)
    reg = await user_service.register(db, "zhangsan", "abc12345", "13800138000")
    with pytest.raises(BizException) as exc:
        await user_service.update_profile(db, reg["id"], {"sex": "2"})
    assert "性别" in str(exc.value)
