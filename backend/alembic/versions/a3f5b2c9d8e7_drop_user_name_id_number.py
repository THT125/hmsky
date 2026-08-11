"""drop user name/id_number

删除 user 表冗余字段:name(昵称,已有 username 可作显示名)与 id_number(身份证号,业务未使用)。

Revision ID: a3f5b2c9d8e7
Revises: 7d7385cd1e8d
Create Date: 2026-08-09 18:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a3f5b2c9d8e7'
down_revision: Union[str, Sequence[str], None] = '7d7385cd1e8d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.drop_column('user', 'name')
    op.drop_column('user', 'id_number')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column('user', sa.Column('name', sa.String(length=32), nullable=True, comment='姓名'))
    op.add_column('user', sa.Column('id_number', sa.String(length=18), nullable=True, comment='身份证号'))
