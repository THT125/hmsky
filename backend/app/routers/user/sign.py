"""C端:每日签到(Bitmap 签到有礼)/user/sign"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.result import ok
from app.core.security import get_current_user
from app.services import sign_service

router = APIRouter(prefix="/user/sign", tags=["C端-签到"])


@router.post("", dependencies=[Depends(get_current_user)])
async def sign(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    每日签到

    返回:
    - Result: {signedToday, consecutiveDays 连续天数, reward 是否触发奖励}。
      连续签到 5 天自动发放 20 元无门槛优惠券。
    """
    return ok(await sign_service.sign(db, user_id))


@router.get("/status", dependencies=[Depends(get_current_user)])
async def status(db: AsyncSession = Depends(get_db), user_id: int = Depends(get_current_user)):
    """
    签到状态:今日是否已签、连续天数、本月签到日历

    返回:
    - Result: {signedToday, consecutiveDays, monthDays 本月签到数组, totalDays 本月总签到天数}。
    """
    return ok(await sign_service.sign_status(db, user_id))
