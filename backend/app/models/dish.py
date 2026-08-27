from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Dish(Base):
    __tablename__ = "dish"
    __table_args__ = {"comment": "菜品"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="菜品名称")
    category_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="菜品分类id")
    price: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), comment="菜品价格")
    image: Mapped[Optional[str]] = mapped_column(String(255), comment="图片")
    description: Mapped[Optional[str]] = mapped_column(String(255), comment="描述信息")
    status: Mapped[Optional[int]] = mapped_column(default=1, comment="0 停售 1 起售")  # 0停售 1起售
    # 库存(NULL=不限量,>=0=剩余份数;下单预扣,取消/拒单/超时回补)
    stock: Mapped[Optional[int]] = mapped_column(Integer, comment="库存(份),NULL=不限量")
    # 自动时间:ORM 层自动填充(行业主流);数据库保留 DEFAULT CURRENT_TIMESTAMP 兜底防绕过 ORM
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    create_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="创建人")
    update_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="修改人")


class DishFlavor(Base):
    __tablename__ = "dish_flavor"
    __table_args__ = {"comment": "菜品口味关系表"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    dish_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="菜品")
    name: Mapped[Optional[str]] = mapped_column(String(32), comment="口味名称")
    value: Mapped[Optional[str]] = mapped_column(String(255), comment="口味数据list")  # JSON数组字符串,如 ["不辣","微辣"]
