"""员工管理(文案与原 EmployeeServiceImpl 一致)"""
import re
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
from app.core.config import ADMIN_TTL
from app.core.exceptions import BizException, LoginFailedException
from app.core.security import SESSION_PREFIX, create_admin_token, new_jti
from app.models import Employee, EmployeeLoginLog
from app.utils.password import hash_password, is_bcrypt, verify_password

DEFAULT_PASSWORD = "123456"


async def _save_session(emp_id: int, jti: str):
    """登录写会话(新登录覆盖旧会话=单端登录);Redis 不可用时降级跳过"""
    try:
        from app.core.redis import redis_setex

        await redis_setex(f"{SESSION_PREFIX}{emp_id}", ADMIN_TTL // 1000, jti)  # ms → s
    except Exception:
        pass


async def _clear_session(emp_id: int):
    """清除会话:删除/禁用/改密后,该员工所有已签发 token 立即失效"""
    try:
        from app.core.redis import redis_delete

        await redis_delete(f"{SESSION_PREFIX}{emp_id}")
    except Exception:
        pass


async def _add_login_log(db: AsyncSession, emp_id: Optional[int], username: str,
                         status: int, ip: str, user_agent: str):
    """写登录日志(成功/失败都记录)"""
    db.add(EmployeeLoginLog(emp_id=emp_id, username=username, status=status,
                            ip=ip, user_agent=(user_agent or "")[:255]))
    await db.commit()


async def login(db: AsyncSession, username: str, password: str, captcha_uuid: str = "",
                captcha_code: str = "", ip: str = "", user_agent: str = "") -> dict:
    """登录:验证码 → 失败锁定 → 密码校验 → 登录日志(成功/失败均记录)"""
    # 1. 图形验证码(用后即焚)
    await verify_captcha(captcha_uuid, captcha_code)
    # 2. 失败锁定检查
    await check_login_locked(username)

    employee = (await db.execute(select(Employee).where(Employee.username == username))).scalar_one_or_none()
    if employee is None:
        await record_login_fail(username)
        await _add_login_log(db, None, username, 0, ip, user_agent)
        raise LoginFailedException("账号不存在")
    if not verify_password(password, employee.password):
        await record_login_fail(username)
        await _add_login_log(db, employee.id, username, 0, ip, user_agent)
        raise LoginFailedException("密码错误")
    if employee.status == 0:
        await _add_login_log(db, employee.id, username, 0, ip, user_agent)
        raise LoginFailedException("账号被锁定")

    # 登录成功:清失败计数 + MD5 懒迁移 + 写会话(旧会话被顶号)
    await clear_login_fail(username)
    if not is_bcrypt(employee.password):
        employee.password = hash_password(password)
        await db.commit()
    jti = new_jti()
    await _save_session(employee.id, jti)
    await _add_login_log(db, employee.id, username, 1, ip, user_agent)
    return {
        "id": employee.id,
        "userName": employee.username,
        "name": employee.name,
        "token": create_admin_token(employee.id, jti),
        "forceChangePassword": employee.force_change_password == 1,
    }


async def save(db: AsyncSession, operator_id: int, name: str, username: str, phone: str,
               sex: str, id_number: str, password: Optional[str] = None):
    validate_phone(phone)
    exists = (await db.execute(select(Employee).where(Employee.username == username))).scalar_one_or_none()
    if exists is not None:
        raise BizException(f"{username}用户名已被注册")
    # 初始密码:管理员显式设置则校验强度直接生效;不设置则默认 123456 并强制首次登录改密
    if password:
        validate_password_strength(password)
        stored_pwd = hash_password(password)
        force_change = 0
    else:
        stored_pwd = hash_password(DEFAULT_PASSWORD)
        force_change = 1
    emp = Employee(
        name=name,
        username=username,
        phone=phone,
        sex=sex,
        id_number=id_number,
        password=stored_pwd,
        status=1,
        force_change_password=force_change,
        create_user=operator_id,  # 创建人(当前登录管理员)
    )
    db.add(emp)
    await db.commit()
    return emp


async def update(db: AsyncSession, operator_id: int, emp_id: int, name: str, username: str, phone: str, sex: str, id_number: str):
    validate_phone(phone)
    emp = await get_by_id(db, emp_id)
    emp.name = name
    emp.username = username
    emp.phone = phone
    emp.sex = sex
    emp.id_number = id_number
    emp.update_user = operator_id  # 修改人(当前登录管理员)
    await db.commit()
    return emp


async def page_query(db: AsyncSession, name: Optional[str], page: int, page_size: int) -> tuple[int, list]:
    conds = []
    if name:
        conds.append(Employee.name.like(f"%{name}%"))
    total = (await db.scalar(select(func.count(Employee.id)).where(*conds))) or 0
    result = await db.execute(
        select(Employee)
        .where(*conds)
        .order_by(Employee.create_time.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    return total, list(result.scalars().all())


async def get_by_id(db: AsyncSession, emp_id: int) -> Employee:
    emp = await db.get(Employee, emp_id)
    if emp is None:
        raise BizException("员工id不存在")
    return emp


async def delete(db: AsyncSession, operator_id: int, emp_id: int):
    """删除员工:禁止删除当前登录账号与内置管理员(admin)"""
    emp = await get_by_id(db, emp_id)
    if emp_id == operator_id:
        raise BizException("不能删除当前登录账号")
    if emp.username == "admin":
        raise BizException("内置管理员账号不允许删除")
    await _clear_session(emp_id)  # 删除即踢下线:旧 token 立即失效
    await db.delete(emp)
    await db.commit()


async def change_status(db: AsyncSession, operator_id: int, emp_id: int, status: int):
    emp = await get_by_id(db, emp_id)
    if emp_id == operator_id:
        raise BizException("不能禁用当前登录账号")
    if status == 0 and emp.username == "admin":
        raise BizException("内置管理员账号不允许禁用")
    emp.status = status
    emp.update_user = operator_id  # 修改人(当前登录管理员)
    if status == 0:
        await _clear_session(emp_id)  # 禁用即踢下线:旧 token 立即失效
    await db.commit()


async def edit_password(db: AsyncSession, operator_id: int, emp_id: int, old_password: str, new_password: str) -> bool:
    emp = await get_by_id(db, emp_id)
    if not verify_password(old_password, emp.password):
        raise BizException("原密码不正确")
    validate_password_strength(new_password)
    emp.password = hash_password(new_password)
    emp.force_change_password = 0  # 改密后解除强制改密
    emp.update_user = operator_id  # 修改人(当前登录管理员)
    self_changed = emp_id == operator_id
    await _clear_session(emp_id)  # 改密即吊销该账号全部旧 token(含本人当前会话)
    await db.commit()
    return self_changed


async def count_by_username(db: AsyncSession, username: str) -> int:
    return (await db.scalar(select(func.count(Employee.id)).where(Employee.username == username))) or 0


async def get_by_username(db: AsyncSession, username: str) -> Optional[Employee]:
    return (await db.execute(select(Employee).where(Employee.username == username))).scalar_one_or_none()


async def any_locked(db: AsyncSession) -> bool:
    return ((await db.scalar(select(func.count(Employee.id)).where(Employee.status == 0))) or 0) > 0
