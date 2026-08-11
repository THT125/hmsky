from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Setmeal(Base):
    __tablename__ = "setmeal"
    __table_args__ = {"comment": "套餐"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    category_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="菜品分类id")
    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="套餐名称")
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="套餐价格")
    status: Mapped[Optional[int]] = mapped_column(default=1, comment="售卖状态 0:停售 1:起售")  # 0停售 1起售
    description: Mapped[Optional[str]] = mapped_column(String(255), comment="描述信息")
    image: Mapped[Optional[str]] = mapped_column(String(255), comment="图片")
    # 自动时间:ORM 层自动填充(行业主流);数据库保留 DEFAULT CURRENT_TIMESTAMP 兜底防绕过 ORM
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    create_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="创建人")
    update_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="修改人")


class SetmealDish(Base):
    __tablename__ = "setmeal_dish"
    __table_args__ = {"comment": "套餐菜品关系"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    setmeal_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="套餐id")
    dish_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="菜品id")
    name: Mapped[Optional[str]] = mapped_column(String(32), comment="菜品名称 （冗余字段）")  # 冗余
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), comment="菜品单价（冗余字段）")  # 冗余
    copies: Mapped[Optional[int]] = mapped_column(comment="菜品份数")
