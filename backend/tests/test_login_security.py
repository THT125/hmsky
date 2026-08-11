"""登录安全单元测试:密码强度校验、验证码校验、失败锁定(Redis 打桩)"""
import pytest

from app.core import auth_guard
from app.core.exceptions import BizException, LoginFailedException
from app.core.security import create_jwt, get_current_admin

SECRET = "test-secret-key-for-unit-tests-0123456789abcdef"


# ===== 密码强度 =====

@pytest.mark.parametrize("password", ["123456", "abcdefgh", "a1", "A" * 20])
def test_weak_password_rejected(password):
    """弱密码(短/纯数字/纯字母/无数字)被拒"""
    with pytest.raises(BizException):
        auth_guard.validate_password_strength(password)


@pytest.mark.parametrize("password", ["abc12345", "Password1", "qwer1234x"])
def test_strong_password_accepted(password):
    """强密码(≥8位且含字母数字)通过"""
    auth_guard.validate_password_strength(password)


# ===== 手机号格式 =====

@pytest.mark.parametrize("phone", ["12345", "23800000000", "138000000001", "1380000000a", ""])
def test_invalid_phone_rejected(phone):
    """非法手机号被拒(长度/开头/含字母)"""
    with pytest.raises(BizException):
        auth_guard.validate_phone(phone)


@pytest.mark.parametrize("phone", ["13800000000", "19912345678", "15012345678"])
def test_valid_phone_accepted(phone):
    """合法手机号通过"""
    auth_guard.validate_phone(phone)


# ===== 验证码校验 =====

async def test_captcha_required():
    """缺失验证码被拒(校验始终执行,CAPTCHA_ENABLED 仅控制接口是否泄露明文)"""
    with pytest.raises(LoginFailedException):
        await auth_guard.verify_captcha("", "")


async def test_captcha_redis_down_passed(monkeypatch):
    """Redis 不可用时验证码校验降级放行"""
    async def fake_get(key):
        raise ConnectionError("redis down")

    async def fake_delete(key):
        pass

    monkeypatch.setattr(auth_guard, "redis_get", fake_get)
    monkeypatch.setattr(auth_guard, "redis_delete", fake_delete)
    await auth_guard.verify_captcha("uuid-x", "1234")  # 不抛异常


async def test_captcha_wrong_code_rejected(monkeypatch):
    """验证码错误被拒"""
    async def fake_get(key):
        return "1234"

    async def fake_delete(key):
        pass

    monkeypatch.setattr(auth_guard, "redis_get", fake_get)
    monkeypatch.setattr(auth_guard, "redis_delete", fake_delete)
    with pytest.raises(LoginFailedException):
        await auth_guard.verify_captcha("uuid-x", "9999")


async def test_captcha_correct_code_passed(monkeypatch):
    """验证码正确通过"""
    async def fake_get(key):
        return "1234"

    async def fake_delete(key):
        pass

    monkeypatch.setattr(auth_guard, "redis_get", fake_get)
    monkeypatch.setattr(auth_guard, "redis_delete", fake_delete)
    await auth_guard.verify_captcha("uuid-x", "1234")  # 不抛异常


# ===== 失败锁定 =====

async def test_login_locked_after_max_fails(monkeypatch):
    """连续失败达到阈值后锁定"""
    monkeypatch.setattr(auth_guard, "LOGIN_FAIL_MAX", 5)

    async def fake_get(key):
        return "5"  # 已失败 5 次

    monkeypatch.setattr(auth_guard, "redis_get", fake_get)
    with pytest.raises(LoginFailedException) as exc:
        await auth_guard.check_login_locked("admin")
    assert "锁定" in str(exc.value)


async def test_login_not_locked_below_max(monkeypatch):
    """失败次数未达阈值不锁定"""
    monkeypatch.setattr(auth_guard, "LOGIN_FAIL_MAX", 5)

    async def fake_get(key):
        return "2"

    monkeypatch.setattr(auth_guard, "redis_get", fake_get)
    await auth_guard.check_login_locked("admin")  # 不抛异常


# ===== token 黑名单 =====

async def test_blacklisted_token_rejected(monkeypatch):
    """被拉黑的 token 校验失败"""
    from app.core import security
    from app.core.exceptions import LoginFailedException as LFE

    monkeypatch.setattr(security, "ADMIN_SECRET_KEY", SECRET)  # 用测试密钥
    token = create_jwt(SECRET, 7200000, {"empId": 1})

    async def fake_is_blacklisted(t):
        return t == token

    monkeypatch.setattr(security, "_is_blacklisted", fake_is_blacklisted)
    with pytest.raises(LFE):
        await get_current_admin(token=token)


async def test_non_blacklisted_token_passed(monkeypatch):
    """未拉黑的 token 正常通过(会话校验通过)"""
    from app.core import security

    monkeypatch.setattr(security, "ADMIN_SECRET_KEY", SECRET)  # 用测试密钥
    token = create_jwt(SECRET, 7200000, {"empId": 1, "jti": "jti-x"})

    async def fake_is_blacklisted(t):
        return False

    async def fake_verify(session_key, jti):
        assert session_key == f"{security.SESSION_PREFIX}1" and jti == "jti-x"

    monkeypatch.setattr(security, "_is_blacklisted", fake_is_blacklisted)
    monkeypatch.setattr(security, "_verify_session", fake_verify)
    assert await get_current_admin(token=token) == 1
