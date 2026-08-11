"""C端:图形验证码 /user/captcha(白名单,无需token;与管理端共用生成逻辑)"""
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core.captcha import generate_captcha
from app.core.config import CAPTCHA_ENABLED
from app.core.redis import redis_setex

router = APIRouter(prefix="/user/captcha", tags=["C端-验证码"])

CAPTCHA_TTL = 300  # 验证码 5 分钟有效


@router.get("")
async def get_captcha():
    """
    获取图形验证码

    参数:
    - 无

    返回:
    - Result: {uuid 验证码标识, image base64图片}。
      CAPTCHA_ENABLED=0 时额外返回 code 明文(测试/联调模式,生产不返回)。
    """
    import uuid as uuid_lib

    code, image = generate_captcha()
    cid = uuid_lib.uuid4().hex
    try:
        await redis_setex(f"captcha:{cid}", CAPTCHA_TTL, code)
    except Exception:
        pass  # Redis 不可用:验证码校验将降级放行
    data = {"uuid": cid, "image": image}
    if not CAPTCHA_ENABLED:
        data["code"] = code  # 测试模式返回明文,便于自动化测试
    return JSONResponse({"code": 1, "msg": None, "data": data})
