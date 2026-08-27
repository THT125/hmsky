"""C端用户注册/登录/资料(账号密码制:用户名+密码+图形验证码)"""
import logging
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_guard import (
    check_login_locked,
    clear_login_fail,
    record_login_fail,
    validate_password_strength,
    validate_phone,
    verify_captcha,
)
from app.core.config import USER_TTL
from app.core.exceptions import BizException, LoginFailedException
from app.core.security import SESSION_USER_PREFIX, create_user_token, new_jti
from app.models import User, UserLoginLog
from app.utils.password import hash_password, verify_password

logger = logging.getLogger("uvicorn.error")


async def _save_session(user_id: int, jti: str):
    """登录写会话(新登录覆盖旧会话=单端登录);Redis 不可用时降级跳过"""
    try:
        from app.core.redis import redis_setex

        await redis_setex(f"{SESSION_USER_PREFIX}{user_id}", USER_TTL // 1000, jti)  # ms → s
    except Exception as e:
        logger.warning("写用户会话降级(Redis不可用,该用户无法被即时踢下线): %s", e)


async def _clear_session(user_id: int):
    """清除会话:改密/登出后,该用户所有已签发 token 立即失效"""
    try:
        from app.core.redis import redis_delete

        await redis_delete(f"{SESSION_USER_PREFIX}{user_id}")
    except Exception as e:
        logger.warning("清用户会话降级(Redis不可用,旧token可能暂未失效): %s", e)


async def _add_login_log(db: AsyncSession, user_id: Optional[int],
                         status: int, ip: str, user_agent: str):
    """写登录日志(注册成功也记为成功登录;失败也记录)"""
    db.add(UserLoginLog(user_id=user_id, login_type="account", phone=None,
                        status=status, ip=ip, user_agent=(user_agent or "")[:255]))
    await db.commit()


async def register(db: AsyncSession, username: str, password: str, phone: str,
                   captcha_uuid: str = "", captcha_code: str = "",
                   ip: str = "", user_agent: str = "") -> dict:
    """注册:验证码 → 用户名唯一 → 手机号唯一 → 密码强度 → 创建用户(自动登录)"""
    await verify_captcha(captcha_uuid, captcha_code)
    validate_password_strength(password)
    validate_phone(phone)

    if (await db.scalar(select(func.count(User.id)).where(User.username == username))) > 0:
        raise BizException("用户名已被注册")
    if (await db.scalar(select(func.count(User.id)).where(User.phone == phone))) > 0:
        raise BizException("该手机号已注册")

    user = User(username=username, password=hash_password(password), phone=phone)
    db.add(user)
    await db.commit()
    await db.refresh(user)
    jti = new_jti()
    await _save_session(user.id, jti)  # 注册即自动登录:写入会话
    await _add_login_log(db, user.id, 1, ip, user_agent)
    return {"id": user.id, "username": username, "token": create_user_token(user.id, username, jti)}


async def login(db: AsyncSession, username: str, password: str,
                captcha_uuid: str = "", captcha_code: str = "",
                ip: str = "", user_agent: str = "") -> dict:
    """登录:验证码 → 失败锁定 → 密码校验 → 登录日志"""
    await verify_captcha(captcha_uuid, captcha_code)
    await check_login_locked(username)

    user = (await db.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if user is None:
        await record_login_fail(username)
        await _add_login_log(db, None, 0, ip, user_agent)
        raise LoginFailedException("账号不存在")
    if not user.password or not verify_password(password, user.password):
        await record_login_fail(username)
        await _add_login_log(db, user.id, 0, ip, user_agent)
        raise LoginFailedException("密码错误")

    await clear_login_fail(username)
    jti = new_jti()
    await _save_session(user.id, jti)  # 登录写会话(旧会话被顶号)
    await _add_login_log(db, user.id, 1, ip, user_agent)
    return {"id": user.id, "username": username, "token": create_user_token(user.id, username, jti)}


# ===== 个人资料 =====

async def get_profile(db: AsyncSession, user_id: int) -> dict:
    """查询当前用户资料"""
    user = await db.get(User, user_id)
    if user is None:
        raise BizException("用户不存在")
    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "sex": user.sex,
        "avatar": user.avatar,
        "createTime": user.create_time,
    }


def _validate_profile(data: dict):
    """资料校验:性别枚举"""
    if data.get("sex") not in (None, "", "0", "1"):
        raise BizException("性别参数不正确")


async def change_password(db: AsyncSession, user_id: int, old_password: str, new_password: str):
    """修改密码:校验旧密码 → 强度 → 清会话(旧 token 全部失效,需重新登录)"""
    user = await db.get(User, user_id)
    if user is None:
        raise BizException("用户不存在")
    if not user.password or not verify_password(old_password, user.password):
        raise BizException("原密码不正确")
    validate_password_strength(new_password)
    if verify_password(new_password, user.password):
        raise BizException("新密码不能与旧密码相同")
    user.password = hash_password(new_password)
    await _clear_session(user_id)  # 改密即吊销全部旧 token
    await db.commit()


async def update_profile(db: AsyncSession, user_id: int, data: dict) -> dict:
    """修改个人资料(性别/头像;用户名和手机号不可改)"""
    _validate_profile(data)
    user = await db.get(User, user_id)
    if user is None:
        raise BizException("用户不存在")
    if "sex" in data:
        user.sex = data["sex"] or None
    if "avatar" in data:
        user.avatar = data["avatar"] or None
    await db.commit()
    return await get_profile(db, user_id)
