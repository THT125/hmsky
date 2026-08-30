"""优惠券:券模板(coupon)+ 用户持有(user_coupon)。
抢券核心:Redis Lua 闸门 + 唯一约束防超发,库存字段 stock 与 Redis 保持一致。
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Integer, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Coupon(Base):
    """优惠券模板(发放总量/剩余/每人限领/有效期)"""
    __tablename__ = "coupon"
    __table_args__ = {"comment": "优惠券模板"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[str] = mapped_column(String(50), nullable=False, comment="券名称")
    type: Mapped[int] = mapped_column(nullable=False, comment="类型 1满减 2折扣")  # 1满减 2折扣
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="满减=减免金额;折扣=折扣率(如8.5=85折)")
    min_amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0, comment="使用门槛(满X可用,0=无门槛)")
    total: Mapped[int] = mapped_column(Integer, nullable=False, comment="发放总量")
    stock: Mapped[int] = mapped_column(Integer, nullable=False, comment="剩余量(初始=total,抢券扣减)")
    per_user_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1, comment="每人限领")
    valid_days: Mapped[int] = mapped_column(Integer, nullable=False, default=7, comment="有效天数(领取后N天内有效)")
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="可领开始时间")
    end_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="可领结束时间")
    status: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=1, comment="状态 0停用 1启用")  # 0停用 1启用
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="创建时间")
    update_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), onupdate=func.now(), comment="更新时间")
    create_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="创建人")
    update_user: Mapped[Optional[int]] = mapped_column(BigInteger, comment="修改人")


class UserCoupon(Base):
    """用户持有的优惠券(领取记录,唯一约束防重复领取=防超发数据库兜底)"""
    __tablename__ = "user_coupon"
    __table_args__ = (
        UniqueConstraint("user_id", "coupon_id", name="uk_user_coupon"),
        Index("idx_user_coupon_user", "user_id", "status"),
        {"comment": "用户优惠券"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户id")
    coupon_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="券模板id")
    status: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=0, comment="状态 0未用 1已用 2过期")
    expire_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="过期时间(领取时=领取时间+有效天数)")
    order_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="使用订单id(下期抵扣用)")
    use_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="使用时间")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="领取时间")
