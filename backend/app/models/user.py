from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class User(Base):
    __tablename__ = "user"  # 表名 user 与 Python 关键字无关,显式指定
    __table_args__ = {"comment": "用户信息"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    username: Mapped[Optional[str]] = mapped_column(String(32), unique=True, comment="登录用户名")
    password: Mapped[Optional[str]] = mapped_column(String(64), comment="密码(bcrypt)")
    phone: Mapped[Optional[str]] = mapped_column(String(11), unique=True, comment="手机号(注册必填,用于找回密码/安全验证)")
    sex: Mapped[Optional[str]] = mapped_column(String(2), comment="性别")
    avatar: Mapped[Optional[str]] = mapped_column(String(500), comment="头像")
    # 注册时间:ORM 层自动填充(行业主流);数据库保留 DEFAULT CURRENT_TIMESTAMP 兜底防绕过 ORM
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
