"""shopping_cart.create_time 增加数据库层默认值 CURRENT_TIMESTAMP

Revision ID: 6bcc11d23270
Revises: 21c82e2d3913
Create Date: 2026-08-06 15:01:00.497288

注意:autogenerate 生成的原始版本包含大量"删除列注释/类型改回"等历史噪音
(模型未写 comment 而数据库已有,属重构时的既有差异),审查后已全部移除,
只保留本次唯一意图:create_time 的 server_default。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '6bcc11d23270'
down_revision: Union[str, Sequence[str], None] = '21c82e2d3913'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column(
        'shopping_cart', 'create_time',
        existing_type=mysql.DATETIME(),
        server_default=sa.text('CURRENT_TIMESTAMP'),  # 插入未显式赋值时由数据库自动填充
        existing_nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column(
        'shopping_cart', 'create_time',
        existing_type=mysql.DATETIME(),
        server_default=None,  # 移除默认值,恢复原样
        existing_nullable=True,
    )
