"""baseline

Revision ID: 21c82e2d3913
Revises:
Create Date: 2026-08-05 17:24:29.654465

说明: 数据库表已由 init.sql 创建,此为空 baseline 迁移。
后续 schema 变更通过 alembic revision --autogenerate 生成。
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '21c82e2d3913'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """baseline: 表已存在,无需变更"""
    pass


def downgrade() -> None:
    """baseline: 无操作"""
    pass
