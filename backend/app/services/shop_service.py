"""店铺营业状态(存 MySQL shop_status 表,替代原项目 Redis)"""
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ShopStatus


async def get_status(db: AsyncSession) -> int:
    row = await db.get(ShopStatus, 1)
    if row is None:
        row = ShopStatus(id=1, status=1)
        db.add(row)
        await db.commit()
        return 1
    return row.status


async def set_status(db: AsyncSession, status: int):
    row = await db.get(ShopStatus, 1)
    if row is None:
        row = ShopStatus(id=1, status=status)
        db.add(row)
    else:
        row.status = status
    await db.commit()
