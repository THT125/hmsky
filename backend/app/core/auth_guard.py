"""登录安全公共逻辑:图形验证码校验、失败锁定、密码强度(管理端/用户端共用)"""
import logging
import re

from app.core.config import LOGIN_FAIL_LOCK_MINUTES, LOGIN_FAIL_MAX
from app.core.exceptions import BizException, LoginFailedException
from app.core.redis import redis_delete, redis_get, redis_incr

logger = logging.getLogger("uvicorn.error")

_CAPTCHA_PREFIX = "captcha:"
_FAIL_PREFIX = "login_fail:"


# ===== 图形验证码 =====

async def verify_captcha(uuid: str, code: str):
    """校验图形验证码(一次性,用后即焚)。
    始终校验(CAPTCHA_ENABLED 仅控制接口是否返回明文 code 给调用方);
    Redis 不可用时降级放行(与缓存降级策略一致)。
    """
    if not uuid or not code:
        raise LoginFailedException("请输入验证码")
    try:
        saved = await redis_get(f"{_CAPTCHA_PREFIX}{uuid}")
    except Exception as e:
        logger.warning("验证码校验降级(Redis不可用,放行): %s", e)
        return  # Redis 不可用:放行
    await redis_delete(f"{_CAPTCHA_PREFIX}{uuid}")  # 一次性,无论对错都销毁
    if saved is None or saved != code:
        raise LoginFailedException("验证码错误或已过期")


# ===== 登录失败锁定 =====

async def check_login_locked(username: str):
    """连续失败超过阈值则锁定一段时间"""
    try:
        count = int(await redis_get(f"{_FAIL_PREFIX}{username}") or 0)
    except Exception as e:
        logger.warning("失败计数读取降级(Redis不可用,不锁定): %s", e)
        count = 0  # Redis 不可用:不锁定
    if count >= LOGIN_FAIL_MAX:
        raise LoginFailedException(f"登录失败次数过多，账号已锁定{LOGIN_FAIL_LOCK_MINUTES}分钟")


async def record_login_fail(username: str):
    """记录失败次数(带 TTL 自动过期解锁)"""
    try:
        await redis_incr(f"{_FAIL_PREFIX}{username}", LOGIN_FAIL_LOCK_MINUTES * 60)
    except Exception as e:
        logger.warning("记录失败次数降级(Redis不可用,锁定防护暂失效): %s", e)


async def clear_login_fail(username: str):
    """登录成功清零失败计数"""
    try:
        await redis_delete(f"{_FAIL_PREFIX}{username}")
    except Exception as e:
        logger.warning("清零失败计数降级(Redis不可用): %s", e)


# ===== 密码强度 =====

def validate_password_strength(password: str):
    """密码强度:至少 8 位,且同时包含字母和数字"""
    if len(password) < 8:
        raise BizException("密码长度至少8位")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise BizException("密码必须同时包含字母和数字")


# ===== 手机号 =====

def validate_phone(phone: str):
    """手机号格式:11 位数字,1 开头(与数据库 varchar(11) 一致,提前拦截脏数据)"""
    if not re.fullmatch(r"1\d{10}", phone):
        raise BizException("手机号格式不正确")
