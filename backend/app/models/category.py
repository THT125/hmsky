from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Category(Base):
    __tablename__ = "category"
    __table_args__ = {"comment": "菜品及套餐分类"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    type: Mapped[Optional[int]] = mapped_column(comment="类型   1 菜品分类 2 套餐分类")  # 1菜品分类 2套餐分类
    name: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="分类名称")
    sort: Mapped[int] = mapped_column(nullable=False, default=0, comment="顺序")
    status: Mapped[Optional[int]] = mapped_column(comment="分类状态 0:禁用，1:启用")  # 0禁用 1启用
    # 自动时间:ORM 层自动填充(行业主流);数据库保留 DEFAULT CURRENT_TIMESTAMP 兜底防绕过 ORM
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    create_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="创建人")
    update_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="修改人")
