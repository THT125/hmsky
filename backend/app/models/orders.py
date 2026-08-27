"""订单与订单明细。
状态:1待付款 2待接单 3已接单 4派送中 5已完成 6已取消 7退款
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Orders(Base):
    __tablename__ = "orders"
    __table_args__ = {"comment": "订单表"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    number: Mapped[Optional[str]] = mapped_column(String(50), comment="订单号")
    status: Mapped[int] = mapped_column(nullable=False, default=1, comment="订单状态 1待付款 2待接单 3已接单 4派送中 5已完成 6已取消 7退款")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="下单用户")
    address_book_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="地址id")
    order_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, comment="下单时间")
    checkout_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="结账时间")
    pay_method: Mapped[int] = mapped_column(nullable=False, default=1, comment="支付方式 1微信,2支付宝")  # 1微信 2支付宝
    pay_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=0, comment="支付状态 0未支付 1已支付 2退款")  # 0未支付 1已支付 2退款
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="实收金额")
    remark: Mapped[Optional[str]] = mapped_column(String(100), comment="备注")
    phone: Mapped[Optional[str]] = mapped_column(String(11), comment="手机号")
    address: Mapped[Optional[str]] = mapped_column(String(255), comment="地址")
    user_name: Mapped[Optional[str]] = mapped_column(String(32), comment="用户名称")
    consignee: Mapped[Optional[str]] = mapped_column(String(32), comment="收货人")
    cancel_reason: Mapped[Optional[str]] = mapped_column(String(255), comment="订单取消原因")
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(255), comment="订单拒绝原因")
    cancel_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="订单取消时间")
    estimated_delivery_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="预计送达时间")
    delivery_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=1, comment="配送状态  1立即送出  0选择具体时间")  # 1立即送出 0选择具体时间
    delivery_time: Mapped[Optional[datetime]] = mapped_column(DateTime, comment="送达时间")
    pack_amount: Mapped[Optional[int]] = mapped_column(comment="打包费")
    tableware_number: Mapped[Optional[int]] = mapped_column(comment="餐具数量")
    tableware_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=1, comment="餐具数量状态  1按餐量提供  0选择具体数量")  # 1按餐量提供 0选择数量
    # 库存回补幂等标志:0未回补 1已回补(防超时任务与取消并发双回补)
    stock_restored: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=0, server_default="0", comment="库存是否已回补 0否 1是")


class OrderDetail(Base):
    __tablename__ = "order_detail"
    __table_args__ = {"comment": "订单明细表"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    name: Mapped[Optional[str]] = mapped_column(String(32), comment="名字")
    image: Mapped[Optional[str]] = mapped_column(String(255), comment="图片")
    order_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="订单id")
    dish_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="菜品id")
    setmeal_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="套餐id")
    dish_flavor: Mapped[Optional[str]] = mapped_column(String(50), comment="口味")
    number: Mapped[int] = mapped_column(nullable=False, default=1, comment="数量")
    amount: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, comment="金额")
