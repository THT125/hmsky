from sqlalchemy import Integer
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShopStatus(Base):
    """店铺营业状态(替代原项目 Redis key SHOP_STATUS),单行数据 id=1"""
    __tablename__ = "shop_status"
    __table_args__ = {"comment": "店铺营业状态"}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="1营业 0打烊")  # 1营业 0打烊
