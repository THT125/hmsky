from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ShoppingCart(Base):
    __tablename__ = "shopping_cart"
    __table_args__ = {"comment": "购物车"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[Optional[str]] = mapped_column(String(32), comment="商品名称")
    image: Mapped[Optional[str]] = mapped_column(String(255), comment="图片")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="主键")  # 数据库注释原文如此(原项目笔误)
    dish_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="菜品id")
    setmeal_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="套餐id")
    dish_flavor: Mapped[Optional[str]] = mapped_column(String(50), comment="口味")
    number: Mapped[int] = mapped_column(nullable=False, default=1, comment="数量")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="金额")
    # 创建时间:ORM 层自动填充(行业主流);数据库保留 DEFAULT CURRENT_TIMESTAMP 兜底防绕过 ORM
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
