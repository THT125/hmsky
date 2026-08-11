"""会话管理单元测试:登录写会话、鉴权校验会话、删除/禁用/改密清会话(Redis 打桩)"""
import pytest

from app.core.exceptions import BizException, LoginFailedException
from app.core.security import (
    SESSION_PREFIX,
    SESSION_USER_PREFIX,
    _verify_session,
    create_user_token,
    get_current_admin,
    get_current_user,
    new_jti,
)
from app.services import employee_service, user_service

SECRET = "test-secret-key-for-unit-tests-0123456789abcdef"


# ===== 会话校验(_verify_session)=====

async def test_session_missing_rejected(monkeypatch):
    """会话不存在(未登录/已被清除)→ 拒绝"""
    async def fake_get(key):
        return None
    monkeypatch.setattr("app.core.redis.redis_get", fake_get)
    with pytest.raises(LoginFailedException) as exc:
        await _verify_session(1, "jti-x")
    assert "失效" in str(exc.value)


async def test_session_match_passed(monkeypatch):
    """jti 与会话一致 → 通过"""
    async def fake_get(key):
        assert key == f"{SESSION_PREFIX}1"
        return "jti-x"
    monkeypatch.setattr("app.core.redis.redis_get", fake_get)
    await _verify_session(1, "jti-x")  # 不抛异常


async def test_session_mismatch_rejected(monkeypatch):
    """jti 不一致(被新登录顶号)→ 拒绝"""
    async def fake_get(key):
        return "jti-new"
    monkeypatch.setattr("app.core.redis.redis_get", fake_get)
    with pytest.raises(LoginFailedException):
        await _verify_session(1, "jti-old")


async def test_session_no_jti_rejected(monkeypatch):
    """token 缺 jti(旧版 token)→ 拒绝"""
    with pytest.raises(LoginFailedException) as exc:
        await _verify_session(1, None)
    assert "不合法" in str(exc.value)


async def test_session_redis_down_passed(monkeypatch):
    """Redis 不可用 → 降级放行(缓存故障不阻塞业务)"""
    async def fake_get(key):
        raise ConnectionError("redis down")
    monkeypatch.setattr("app.core.redis.redis_get", fake_get)
    await _verify_session(1, "jti-x")  # 不抛异常


# ===== 鉴权依赖(get_current_admin)=====

async def test_current_admin_requires_session(monkeypatch):
    """无会话的员工 token 被拒(删除/禁用后的即时失效路径)"""
    from app.core import security
    from app.core.security import create_jwt

    monkeypatch.setattr(security, "ADMIN_SECRET_KEY", SECRET)
    token = create_jwt(SECRET, 7200000, {"empId": 1, "jti": "jti-gone"})

    async def fake_blacklisted(t):
        return False

    async def fake_verify(emp_id, jti):
        raise LoginFailedException("token已失效,请重新登录")

    monkeypatch.setattr(security, "_is_blacklisted", fake_blacklisted)
    monkeypatch.setattr(security, "_verify_session", fake_verify)
    with pytest.raises(LoginFailedException):
        await get_current_admin(token=token)


async def test_current_admin_session_passed(monkeypatch):
    """会话正常 → 返回 empId"""
    from app.core import security
    from app.core.security import create_jwt

    monkeypatch.setattr(security, "ADMIN_SECRET_KEY", SECRET)
    token = create_jwt(SECRET, 7200000, {"empId": 7, "jti": "jti-ok"})

    async def fake_blacklisted(t):
        return False

    async def fake_verify(session_key, jti):
        assert session_key == f"{SESSION_PREFIX}7" and jti == "jti-ok"

    monkeypatch.setattr(security, "_is_blacklisted", fake_blacklisted)
    monkeypatch.setattr(security, "_verify_session", fake_verify)
    assert await get_current_admin(token=token) == 7


# ===== 登录写会话 / 删除禁用改密清会话(employee_service)=====

async def test_login_writes_session(monkeypatch):
    """登录成功后写入 session:{empId}=jti,TTL 与 token 一致(秒)"""
    from app.core.config import ADMIN_TTL

    written = {}

    async def fake_setex(key, ttl_seconds, value):
        written[key] = (ttl_seconds, value)

    monkeypatch.setattr("app.core.redis.redis_setex", fake_setex)

    jti = new_jti()
    await employee_service._save_session(99, jti)
    assert written == {f"{SESSION_PREFIX}99": (ADMIN_TTL // 1000, jti)}


async def test_login_session_redis_down_not_block(monkeypatch):
    """Redis 不可用时登录不抛错(降级)"""
    async def fake_setex(key, ttl, value):
        raise ConnectionError("redis down")
    monkeypatch.setattr("app.core.redis.redis_setex", fake_setex)
    await employee_service._save_session(99, new_jti())  # 不抛异常


async def test_delete_clears_session(monkeypatch):
    """删除员工时清除会话"""
    deleted = []

    async def fake_delete(key):
        deleted.append(key)

    monkeypatch.setattr("app.core.redis.redis_delete", fake_delete)
    await employee_service._clear_session(99)
    assert deleted == [f"{SESSION_PREFIX}99"]


async def test_edit_password_self_changed_flag(db, monkeypatch):
    """改密:清会话 + 返回 selfChanged(自己/他人)"""
    emp = await employee_service.save(db, 1, "测试", "test_psw", "13800000000", "1", "110101199001011234")

    deleted = []
    async def fake_delete(key):
        deleted.append(key)
    monkeypatch.setattr("app.core.redis.redis_delete", fake_delete)

    # 改他人密码
    self_changed = await employee_service.edit_password(db, 2, emp.id, "123456", "newpass123")
    assert self_changed is False
    assert deleted == [f"{SESSION_PREFIX}{emp.id}"]

    # 改自己密码
    deleted.clear()
    self_changed = await employee_service.edit_password(db, emp.id, emp.id, "newpass123", "newpass456")
    assert self_changed is True
    assert deleted == [f"{SESSION_PREFIX}{emp.id}"]


# ===== 用户端会话 =====

async def test_user_token_contains_jti(monkeypatch):
    """用户 token 携带 jti(会话标识)"""
    from app.core import security
    from app.core.security import parse_jwt

    monkeypatch.setattr(security, "USER_SECRET_KEY", SECRET)  # 用测试密钥
    token = create_user_token(5, "zhangsan", "jti-user")
    claims = parse_jwt(SECRET, token)
    assert claims["userId"] == 5
    assert claims["jti"] == "jti-user"


async def test_user_register_writes_session(monkeypatch, db):
    """注册(自动登录)写入用户会话,TTL 与 token 一致(秒)"""
    from app.core import security
    from app.core.config import USER_TTL
    from app.core.security import parse_jwt

    monkeypatch.setattr(security, "USER_SECRET_KEY", SECRET)  # 用测试密钥
    async def fake_verify(uuid, code):
        pass

    monkeypatch.setattr(user_service, "verify_captcha", fake_verify)
    written = {}

    async def fake_setex(key, ttl_seconds, value):
        written[key] = (ttl_seconds, value)

    monkeypatch.setattr("app.core.redis.redis_setex", fake_setex)
    reg = await user_service.register(db, "zhangsan", "abc12345", "13800138000")
    key = f"{SESSION_USER_PREFIX}{reg['id']}"
    assert key in written
    assert written[key][0] == USER_TTL // 1000  # TTL(秒)
    claims = parse_jwt(SECRET, reg["token"])
    assert written[key][1] == claims["jti"]  # 会话中的 jti 与 token 内一致


async def test_current_user_requires_session(monkeypatch, db):
    """改密/登出后,用户旧 token 被拒(会话缺失)"""
    from app.core import security
    from app.core.security import create_jwt

    monkeypatch.setattr(security, "USER_SECRET_KEY", SECRET)
    token = create_jwt(SECRET, 7200000, {"userId": 3, "username": "zhangsan", "jti": "jti-gone"})

    async def fake_blacklisted(t):
        return False

    async def fake_get(key):
        return None  # 会话已被清除

    monkeypatch.setattr(security, "_is_blacklisted", fake_blacklisted)
    monkeypatch.setattr("app.core.redis.redis_get", fake_get)
    with pytest.raises(LoginFailedException):
        await get_current_user(authentication=token)


async def test_current_user_session_passed(monkeypatch):
    """用户会话正常 → 返回 userId"""
    from app.core import security
    from app.core.security import create_jwt

    monkeypatch.setattr(security, "USER_SECRET_KEY", SECRET)
    token = create_jwt(SECRET, 7200000, {"userId": 3, "username": "zhangsan", "jti": "jti-ok"})

    async def fake_blacklisted(t):
        return False

    async def fake_get(key):
        assert key == f"{SESSION_USER_PREFIX}3"
        return "jti-ok"

    monkeypatch.setattr(security, "_is_blacklisted", fake_blacklisted)
    monkeypatch.setattr("app.core.redis.redis_get", fake_get)
    assert await get_current_user(authentication=token) == 3


async def test_change_password_clears_session(db, monkeypatch):
    """用户改密:旧密码错拒绝 / 新密码同旧拒绝 / 成功后清会话"""
    async def fake_verify(uuid, code):
        pass

    monkeypatch.setattr(user_service, "verify_captcha", fake_verify)
    deleted = []

    async def fake_delete(key):
        deleted.append(key)

    monkeypatch.setattr("app.core.redis.redis_delete", fake_delete)

    reg = await user_service.register(db, "zhangsan", "abc12345", "13800138000")
    uid = reg["id"]

    # 旧密码错误
    with pytest.raises(BizException) as exc:
        await user_service.change_password(db, uid, "wrong123", "newpass123")
    assert "原密码" in str(exc.value)

    # 新密码与旧密码相同
    with pytest.raises(BizException) as exc:
        await user_service.change_password(db, uid, "abc12345", "abc12345")
    assert "相同" in str(exc.value)

    # 新密码强度不足
    with pytest.raises(BizException) as exc:
        await user_service.change_password(db, uid, "abc12345", "12345678")
    assert "密码" in str(exc.value)

    # 成功:清会话,旧 token 全部失效
    await user_service.change_password(db, uid, "abc12345", "newpass123")
    assert deleted == [f"{SESSION_USER_PREFIX}{uid}"]
