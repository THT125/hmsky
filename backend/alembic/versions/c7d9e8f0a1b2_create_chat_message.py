"""create chat_message

客服聊天消息表:用户↔商家实时沟通,一个用户=一个会话(按 user_id 聚合)。

Revision ID: c7d9e8f0a1b2
Revises: b4c6d8e0f2a1
Create Date: 2026-08-17 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'c7d9e8f0a1b2'
down_revision: Union[str, Sequence[str], None] = 'b4c6d8e0f2a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'chat_message',
        sa.Column('id', mysql.BIGINT(display_width=20), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('user_id', mysql.BIGINT(display_width=20), nullable=False, comment='会话主体(用户)'),
        sa.Column('sender_type', mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=20),
                  nullable=False, comment='发送方 admin/user'),
        sa.Column('sender_id', mysql.BIGINT(display_width=20), nullable=True, comment='发送者id(用户id或员工id)'),
        sa.Column('content', mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=500),
                  nullable=False, comment='消息内容'),
        sa.Column('read_status', mysql.INTEGER(display_width=11), nullable=False, server_default='0',
                  comment='接收方是否已读 0未读 1已读'),
        sa.Column('create_time', mysql.DATETIME(), nullable=True, comment='发送时间'),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_unicode_ci',
        mysql_default_charset='utf8mb4',
        comment='客服聊天消息',
    )
    op.create_index('idx_chat_user', 'chat_message', ['user_id', 'create_time'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_chat_user', table_name='chat_message')
    op.drop_table('chat_message')
