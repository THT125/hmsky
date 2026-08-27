"""客服聊天消息(用户↔商家,一个用户=一个会话,按 user_id 聚合)"""
from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ChatMessage(Base):
    __tablename__ = "chat_message"
    __table_args__ = (
        Index("idx_chat_user", "user_id", "create_time"),  # 会话查询/未读聚合走该索引
        {"comment": "客服聊天消息"},
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True, comment="主键")
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment="会话主体(用户)")
    sender_type: Mapped[str] = mapped_column(String(20), nullable=False, comment="发送方 admin/user")
    sender_id: Mapped[Optional[int]] = mapped_column(BigInteger, comment="发送者id(用户id或员工id)")
    content: Mapped[str] = mapped_column(String(500), nullable=False, comment="消息内容")
    # 接收方是否已读:0未读 1已读(管理端看用户发来的未读数,用户端看商家回复的未读数)
    read_status: Mapped[Optional[int]] = mapped_column(Integer, nullable=False, default=0, comment="接收方是否已读 0未读 1已读")
    create_time: Mapped[Optional[datetime]] = mapped_column(DateTime, default=func.now(), comment="发送时间")
