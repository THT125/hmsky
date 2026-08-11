from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Employee(Base):
    __tablename__ = "employee"
    __table_args__ = {"comment": "员工信息"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(32), nullable=False, comment="姓名")
    username: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, comment="用户名")
    password: Mapped[str] = mapped_column(String(64), nullable=False, comment="密码")
    phone: Mapped[str] = mapped_column(String(11), nullable=False, comment="手机号")
    sex: Mapped[str] = mapped_column(String(2), nullable=False, comment="性别")
    id_number: Mapped[Optional[str]] = mapped_column(String(18), nullable=False, comment="身份证号")
    status: Mapped[Optional[int]] = mapped_column(nullable=False, default=1, comment="状态 0:禁用，1:启用")  # 0禁用 1启用
    force_change_password: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="首次登录是否强制改密 0否 1是")
    # 自动时间:ORM 层自动填充(行业主流);数据库保留 DEFAULT CURRENT_TIMESTAMP 兜底防绕过 ORM
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    create_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="创建人")
    update_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="修改人")
