from typing import Optional

from sqlalchemy import BigInteger, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class AddressBook(Base):
    __tablename__ = "address_book"
    __table_args__ = {"comment": "地址簿"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="用户id")
    consignee: Mapped[Optional[str]] = mapped_column(String(50), comment="收货人")
    sex: Mapped[Optional[str]] = mapped_column(String(2), comment="性别")
    phone: Mapped[str] = mapped_column(String(11), nullable=False, comment="手机号")
    province_code: Mapped[Optional[str]] = mapped_column(String(12), comment="省级区划编号")
    province_name: Mapped[Optional[str]] = mapped_column(String(32), comment="省级名称")
    city_code: Mapped[Optional[str]] = mapped_column(String(12), comment="市级区划编号")
    city_name: Mapped[Optional[str]] = mapped_column(String(32), comment="市级名称")
    district_code: Mapped[Optional[str]] = mapped_column(String(12), comment="区级区划编号")
    district_name: Mapped[Optional[str]] = mapped_column(String(32), comment="区级名称")
    detail: Mapped[Optional[str]] = mapped_column(String(200), comment="详细地址")
    label: Mapped[Optional[str]] = mapped_column(String(100), comment="标签")
    is_default: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=0, comment="默认 0 否 1是")  # 0否 1是
