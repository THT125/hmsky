from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, String, func
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
    # 账号状态:封禁由管理端操作,封禁即踢下线+禁止登录+禁止下单(不做物理删除,订单/券有关联)
    status: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=1, server_default="1", comment="1正常 0封禁")
    ban_reason: Mapped[Optional[str]] = mapped_column(String(255), comment="封禁原因(审计)")
    # 最近登录:登录日志表存完整历史(审计),这里冗余存"最近一次"(详情展示/活跃度筛选)
    last_login_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="最近登录时间")
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(50), comment="最近登录IP")
    # 注册时间:ORM 层自动填充(行业主流);数据库保留 DEFAULT CURRENT_TIMESTAMP 兜底防绕过 ORM
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now())
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    update_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="最后操作人(管理端员工id)")
