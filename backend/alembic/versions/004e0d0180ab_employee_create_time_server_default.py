"""employee.create_time 增加数据库层默认值 CURRENT_TIMESTAMP

Revision ID: 004e0d0180ab
Revises: a02ae5010d08
Create Date: 2026-08-06 21:09:39.546539

注意:autogenerate 未检测到 server_default 变化(MySQL 兼容性已知问题,
shopping_cart 迁移同此),审查后手动补写。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = '004e0d0180ab'
down_revision: Union[str, Sequence[str], None] = 'a02ae5010d08'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'employee', 'create_time',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('CURRENT_TIMESTAMP'),  # 插入未显式赋值时由数据库自动填充
        existing_nullable=True,
        comment='创建时间',  # MySQL ALTER 不带 COMMENT 会清掉注释,必须显式补回
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'employee', 'create_time',
        existing_type=mysql.DATETIME(),
        server_default=None,  # 移除默认值,恢复原样
        existing_nullable=True,
        comment='创建时间',  # 同上,保持注释不丢
    )
