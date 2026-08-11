"""C端:用户注册/登录/资料 /user/user(注册/登录为白名单,其余需登录)"""
from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import USER_SECRET_KEY
from app.core.database import get_db
from app.core.result import ok
from app.core.security import SESSION_USER_PREFIX, blacklist_token, clear_session_by_token, get_current_user
from app.schemas.business import UserChangePasswordIn, UserLoginIn, UserProfileIn, UserRegisterIn
from app.services import user_service

router = APIRouter(prefix="/user/user", tags=["C端-用户"])


def _client_info(request: Request) -> tuple[str, str]:
    """提取客户端 IP 和 UA(登录日志用)"""
    ip = request.client.host if request.client else ""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:  # 经过代理时取真实 IP
        ip = forwarded.split(",")[0].strip()
    return ip, request.headers.get("user-agent", "")


@router.post("/register")
async def register(body: UserRegisterIn, request: Request, db: AsyncSession = Depends(get_db)):
    """
    用户注册(自动登录)

    参数:
    - body (UserRegisterIn): 注册参数模型,包含 username 用户名、password 密码、captchaUuid 验证码标识、captchaCode 验证码。

    返回:
    - Result: {id 用户id, username 用户名, token JWT令牌}。
    """
    ip, ua = _client_info(request)
    return ok(await user_service.register(db, body.username, body.password, body.phone,
                                          body.captcha_uuid or "", body.captcha_code or "",
                                          ip, ua))


@router.post("/login")
async def login(body: UserLoginIn, request: Request, db: AsyncSession = Depends(get_db)):
    """
    用户登录

    参数:
    - body (UserLoginIn): 登录参数模型,包含 username 用户名、password 密码、captchaUuid 验证码标识、captchaCode 验证码。

    返回:
    - Result: {id 用户id, username 用户名, token JWT令牌}。
      登录失败自动记录日志;连续失败 5 次锁定 10 分钟。
    """
    ip, ua = _client_info(request)
    return ok(await user_service.login(db, body.username, body.password,
                                       body.captcha_uuid or "", body.captcha_code or "",
                                       ip, ua))


@router.post("/logout", dependencies=[Depends(get_current_user)])
async def logout(authentication: str = Header(default=None)):
    """
    退出登录

    参数:
    - authentication (str, 可选): 当前登录 token,将加入黑名单并清除会话立即失效。

    返回:
    - Result: 退出成功。
    """
    await blacklist_token(authentication or "", USER_SECRET_KEY)
    await clear_session_by_token(authentication or "", USER_SECRET_KEY, SESSION_USER_PREFIX)
    return ok()


@router.put("/password", dependencies=[Depends(get_current_user)])
async def change_password(body: UserChangePasswordIn, db: AsyncSession = Depends(get_db),
                          user_id: int = Depends(get_current_user)):
    """
    修改密码

    参数:
    - body (UserChangePasswordIn): 修改密码参数模型,包含 oldPassword 旧密码、newPassword 新密码。

    返回:
    - Result: 修改成功。改密后本账号所有旧 token 立即失效,需重新登录。
    """
    await user_service.change_password(db, user_id, body.old_password, body.new_password)
    return ok({"selfChanged": True})


@router.get("/profile", dependencies=[Depends(get_current_user)])
async def get_profile(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    查询当前用户资料

    参数:
    - db (Session): 数据库会话。
    - user_id (int): 当前登录用户id。

    返回:
    - Result: {id, username 用户名, phone 手机号, sex 性别, avatar 头像, createTime 注册时间}。
    """
    return ok(await user_service.get_profile(db, user_id))


@router.put("/profile", dependencies=[Depends(get_current_user)])
async def update_profile(body: UserProfileIn, db: AsyncSession = Depends(get_db),
                         user_id: int = Depends(get_current_user)):
    """
    修改个人资料

    参数:
    - body (UserProfileIn): 资料参数模型,包含 sex 性别、avatar 头像。
      用户名和手机号不可修改(涉及安全验证,后续提供独立流程)。

    返回:
    - Result: 修改后的完整资料。
    """
    return ok(await user_service.update_profile(db, user_id, body.model_dump(exclude_unset=True)))
