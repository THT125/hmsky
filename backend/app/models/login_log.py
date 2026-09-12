"""登录日志:管理端员工登录日志 + 用户端登录日志(安全审计)"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class EmployeeLoginLog(Base):
    """管理端登录日志(谁在何时何地登录成功/失败)"""
    __tablename__ = "employee_login_log"
    __table_args__ = {"comment": "管理端登录日志"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    emp_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="员工id(登录失败时可能为空)")
    username: Mapped[str] = mapped_column(String(32), nullable=False, comment="登录用户名")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="1成功 0失败")
    ip: Mapped[Optional[str]] = mapped_column(String(50), comment="登录IP")
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), comment="浏览器UA")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="登录时间")


class UserLoginLog(Base):
    """用户端登录日志(微信/手机号登录审计)"""
    __tablename__ = "user_login_log"
    # 索引服务于风控分析(按用户聚合 IP 分散度 / 按 IP 聚合多账号),并支撑详情页登录日志分页
    __table_args__ = (
        Index("idx_ull_user_time", "user_id", "create_time"),
        Index("idx_ull_ip_time", "ip", "create_time"),
        {"comment": "用户端登录日志"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="用户id(登录失败时可能为空)")
    login_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="登录方式 account(账号密码)")
    phone: Mapped[Optional[str]] = mapped_column(String(11), comment="手机号(预留,当前账号制未使用)")
    status: Mapped[int] = mapped_column(Integer, nullable=False, default=0, comment="1成功 0失败")
    ip: Mapped[Optional[str]] = mapped_column(String(50), comment="登录IP")
    user_agent: Mapped[Optional[str]] = mapped_column(String(255), comment="浏览器UA")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="登录时间")
