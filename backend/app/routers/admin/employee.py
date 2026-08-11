"""管理端:员工管理 /admin/employee"""
from typing import Optional

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.pagination import page_result
from app.core.result import ok
from app.core.security import blacklist_token, get_current_admin
from app.schemas.business import EmployeeEditPasswordIn, EmployeeIn, EmployeeLoginIn
from app.services import employee_service
from app.utils.orm import to_camel_dict

router = APIRouter(prefix="/admin/employee", tags=["员工管理"])


def _client_info(request: Request) -> tuple[str, str]:
    """提取客户端 IP 和 UA(登录日志用)"""
    ip = request.client.host if request.client else ""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:  # 经过代理时取真实 IP
        ip = forwarded.split(",")[0].strip()
    return ip, request.headers.get("user-agent", "")


@router.post("/login")
async def login(body: EmployeeLoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    """
    员工登录

    参数:
    - body (EmployeeLoginIn): 登录参数模型,包含 username 用户名、password 密码、captchaUuid 验证码标识、captchaCode 验证码。

    返回:
    - Result: 登录成功返回 {id, userName, name, token, forceChangePassword}。
      登录失败自动记录登录日志;连续失败 5 次锁定 10 分钟。
    """
    ip, ua = _client_info(request)
    return ok(await employee_service.login(db, body.username, body.password,
                                           body.captcha_uuid or "", body.captcha_code or "",
                                           ip, ua))


@router.post("/logout")
async def logout(token: str = Header(default=None)):
    """
    退出登录

    参数:
    - token (str, 可选): 当前登录 token,将加入黑名单并清除会话立即失效。

    返回:
    - Result: 退出成功。
    """
    from app.core.config import ADMIN_SECRET_KEY
    from app.core.security import SESSION_PREFIX, clear_session_by_token

    await blacklist_token(token or "", ADMIN_SECRET_KEY)
    await clear_session_by_token(token or "", ADMIN_SECRET_KEY, SESSION_PREFIX)
    return ok()


@router.post("")
async def save(
    body: EmployeeIn,
    db: AsyncSession = Depends(get_db),
    emp_id: int = Depends(get_current_admin)):
    """
    新增员工

    参数:
    - body (EmployeeIn): 员工信息模型,包含 name 姓名、username 用户名、phone 手机号、sex 性别、
      idNumber 身份证号、password 初始密码(可选,不填默认 123456 并强制首次登录改密)。

    返回:
    - Result: 新增成功(create_user 记录当前操作人)。
    """
    await employee_service.save(db, emp_id, body.name, body.username, body.phone, body.sex,
                                body.id_number, body.password)
    return ok()


@router.put("")
async def update(
    body: EmployeeIn,
    db: AsyncSession = Depends(get_db),
    emp_id: int = Depends(get_current_admin)):
    """
    编辑员工信息

    参数:
    - body (EmployeeIn): 员工信息模型,包含 id 员工id及需要修改的字段。

    返回:
    - Result: 编辑成功(update_user 记录当前操作人)。
    """
    await employee_service.update(db, emp_id, body.id, body.name, body.username, body.phone, body.sex, body.id_number)
    return ok()


@router.put("/editPassword")
async def edit_password(
    body: EmployeeEditPasswordIn,
    db: AsyncSession = Depends(get_db),
    emp_id: int = Depends(get_current_admin)):
    """
    修改密码

    参数:
    - body (EmployeeEditPasswordIn): 修改密码参数模型,包含 empId 员工id、oldPassword 旧密码、newPassword 新密码。

    返回:
    - Result: 修改成功(update_user 记录当前操作人;selfChanged=true 表示改的是自己,
      该账号所有旧 token 已失效,前端需引导重新登录)。
    """
    self_changed = await employee_service.edit_password(db, emp_id, body.emp_id, body.old_password, body.new_password)
    return ok({"selfChanged": self_changed})


@router.get("/page", dependencies=[Depends(get_current_admin)])
async def page(name: Optional[str] = None,
               page: int = Query(1),
               pageSize: int = Query(10, alias="pageSize"),
               db: AsyncSession = Depends(get_db)):
    """
    员工分页查询

    参数:
    - name (str, 可选): 员工姓名关键字,模糊查询。
    - page (int): 页码,默认1。
    - pageSize (int): 每页条数,默认10。
    - db (Session): 数据库会话。

    返回:
    - Result: 分页结果 {total, records}。
    """
    total, rows = await employee_service.page_query(db, name, page, pageSize)
    return ok(page_result(total, [to_camel_dict(r) for r in rows]))


@router.delete("/{emp_id}")
async def delete(emp_id: int, db: AsyncSession = Depends(get_db),
                 operator_id: int = Depends(get_current_admin)):
    """
    删除员工

    参数:
    - emp_id (int): 员工id。

    返回:
    - Result: 删除成功。禁止删除当前登录账号与内置管理员(admin)。
    """
    await employee_service.delete(db, operator_id, emp_id)
    return ok()


@router.get("/{emp_id}", dependencies=[Depends(get_current_admin)])
async def get_by_id(emp_id: int, db: AsyncSession = Depends(get_db)):
    """
    根据id查询员工

    参数:
    - emp_id (int): 员工id。

    返回:
    - Result: 员工信息。
    """
    emp = await employee_service.get_by_id(db, emp_id)
    return ok({
        "id": emp.id, "name": emp.name, "username": emp.username,
        "phone": emp.phone, "sex": emp.sex, "idNumber": emp.id_number,
        "status": emp.status, "createTime": emp.create_time,
    })


@router.post("/status/{status}")
async def change_status(status: int, id: int = Query(...), db: AsyncSession = Depends(get_db),
                        emp_id: int = Depends(get_current_admin)):
    """
    启用、禁用员工账号

    参数:
    - status (int): 目标状态,1启用 0禁用。
    - id (int): 员工id。

    返回:
    - Result: 操作成功(update_user 记录当前操作人)。
    """
    await employee_service.change_status(db, emp_id, id, status)
    return ok()
