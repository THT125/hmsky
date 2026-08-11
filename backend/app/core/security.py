"""JWT 签发/校验与登录态依赖注入。
- 管理端 token 放在请求头 token 中
- 用户端 token 放在请求头 authentication 中
- 登出后 token 进入 Redis 黑名单(校验时拦截),Redis 不可用时降级跳过
- 会话管理:登录时写入 session:{empId}=jti(新登录覆盖=单端登录);
  删除/禁用/改密时清除会话,该员工所有已签发 token 立即失效
"""
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Header

from app.core.config import (
    ADMIN_SECRET_KEY,
    ADMIN_TTL,
    USER_SECRET_KEY,
    USER_TTL,
)
from app.core.exceptions import LoginFailedException
from app.utils.md5 import md5

# token 黑名单 key 前缀
BLACKLIST_PREFIX = "token_blacklist:"
# 会话表 key 前缀:session:emp:{empId} / session:user:{userId} = jti
# (员工与用户 id 各自自增可能撞号,必须区分前缀)
SESSION_PREFIX = "session:emp:"
SESSION_USER_PREFIX = "session:user:"


def create_jwt(secret: str, ttl_ms: int, payload: dict) -> str:
    now = datetime.now(timezone.utc)
    claims = dict(payload)
    claims["iat"] = now
    claims["exp"] = now + timedelta(milliseconds=ttl_ms)
    return jwt.encode(claims, secret, algorithm="HS256")


def parse_jwt(secret: str, token: str) -> dict:
    try:
        return jwt.decode(token, secret, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise LoginFailedException("token已过期")
    except jwt.InvalidTokenError:
        raise LoginFailedException("token不合法")


async def blacklist_token(token: str, secret: str):
    """登出:将 token 加入黑名单,TTL 为其剩余有效期"""
    if not token:
        return
    try:
        from app.core.redis import redis_setex

        claims = parse_jwt(secret, token)
        remaining = int(claims["exp"]) - int(datetime.now(timezone.utc).timestamp())
        if remaining > 0:
            await redis_setex(f"{BLACKLIST_PREFIX}{md5(token)}", remaining, "1")
    except Exception:
        pass  # Redis 不可用或 token 无效时静默(黑名单是增强项,不阻断登出)


async def _is_blacklisted(token: str) -> bool:
    """校验 token 是否在黑名单。Redis 不可用时降级放行(与缓存降级策略一致)"""
    try:
        from app.core.redis import redis_get

        return await redis_get(f"{BLACKLIST_PREFIX}{md5(token)}") is not None
    except Exception:
        return False


async def _verify_session(session_key: str, jti):
    """会话校验:JWT 的 jti 必须与 Redis 中 session key 一致。
    - 会话不存在(从未登录/已被清除,如删除/禁用/改密后)→ 拒绝
    - jti 不一致(被新登录顶号,单端登录)→ 拒绝
    - Redis 不可用 → 降级放行(缓存故障不阻塞业务,与黑名单策略一致)
    """
    try:
        if session_key is None or not jti:
            raise LoginFailedException("token不合法")
        from app.core.redis import redis_get

        current = await redis_get(session_key)
        if current is None or current != jti:
            raise LoginFailedException("token已失效,请重新登录")
    except LoginFailedException:
        raise
    except Exception:
        pass  # Redis 不可用降级放行


async def _clear_session_by_key(session_key: str):
    """清除会话(删除/禁用/改密/登出后旧 token 立即失效)"""
    if not session_key:
        return
    try:
        from app.core.redis import redis_delete

        await redis_delete(session_key)
    except Exception:
        pass  # Redis 不可用降级


async def clear_session_by_token(token: str, secret: str, prefix: str):
    """登出:按 token 解析主体 id 清除其会话"""
    try:
        claims = parse_jwt(secret, token)
        subject_id = claims.get("userId") or claims.get("empId")
        if subject_id is not None:
            await _clear_session_by_key(f"{prefix}{subject_id}")
    except Exception:
        pass  # token 无效/Redis 不可用时静默


async def get_current_admin(token: str = Header(default=None)) -> int:
    """管理端登录态依赖:返回当前员工 id(黑名单 + 会话双重校验)"""
    token = token or ""
    if await _is_blacklisted(token):
        raise LoginFailedException("token已失效,请重新登录")
    claims = parse_jwt(ADMIN_SECRET_KEY, token)
    emp_id = claims.get("empId")
    await _verify_session(f"{SESSION_PREFIX}{emp_id}", claims.get("jti"))
    if emp_id is None:
        raise LoginFailedException("token不合法")
    return emp_id


async def get_current_user(authentication: str = Header(default=None)) -> int:
    """用户端登录态依赖:返回当前用户 id(黑名单 + 会话双重校验)"""
    authentication = authentication or ""
    if await _is_blacklisted(authentication):
        raise LoginFailedException("token已失效,请重新登录")
    claims = parse_jwt(USER_SECRET_KEY, authentication)
    user_id = claims.get("userId")
    await _verify_session(f"{SESSION_USER_PREFIX}{user_id}", claims.get("jti"))
    if user_id is None:
        raise LoginFailedException("token不合法")
    return user_id


def new_jti() -> str:
    """会话唯一标识:登录时生成,同时写入 JWT claims 与 Redis 会话表"""
    return uuid.uuid4().hex


def create_admin_token(emp_id: int, jti: str) -> str:
    return create_jwt(ADMIN_SECRET_KEY, ADMIN_TTL, {"empId": emp_id, "jti": jti})


def create_user_token(user_id: int, username: str, jti: str) -> str:
    return create_jwt(USER_SECRET_KEY, USER_TTL, {"userId": user_id, "username": username, "jti": jti})
