"""auto timestamps for dish setmeal category user

为 4 张表的 create_time 增加数据库默认值 CURRENT_TIMESTAMP(与 shopping_cart/employee 一致)。
注:autogenerate 检测不到 server_default 变化,手写;MySQL ALTER 不带 COMMENT 会清注释,
dish/setmeal/category 必须显式补回,user 本身无注释(传 None 保持一致)。

Revision ID: 7ed80d8f6e97
Revises: 004e0d0180ab
Create Date: 2026-08-06 21:22:45.112101

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


# revision identifiers, used by Alembic.
revision: str = '7ed80d8f6e97'
down_revision: Union[str, Sequence[str], None] = '004e0d0180ab'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (表名, 列注释):user 表 create_time 数据库无注释,保持一致传 None
_TABLES = [("dish", "创建时间"), ("setmeal", "创建时间"), ("category", "创建时间"), ("user", None)]


def upgrade() -> None:
    """Upgrade schema."""
    for table, comment in _TABLES:
        op.alter_column(
            table, 'create_time',
            existing_type=mysql.DATETIME(),
            server_default=sa.text('CURRENT_TIMESTAMP'),  # 插入未显式赋值时由数据库自动填充
            existing_nullable=True,
            comment=comment,
        )


def downgrade() -> None:
    """Downgrade schema."""
    for table, comment in _TABLES:
        op.alter_column(
            table, 'create_time',
            existing_type=mysql.DATETIME(),
            server_default=None,  # 移除默认值,恢复原样
            existing_nullable=True,
            comment=comment,
        )
