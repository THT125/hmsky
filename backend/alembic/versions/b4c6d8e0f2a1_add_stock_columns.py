"""add stock columns

商品库存管理:
- dish/setmeal 加 stock(NULL=不限量,>=0=剩余份数;下单预扣,取消/拒单/超时回补)
- orders 加 stock_restored(回补幂等标志,防超时任务与取消并发双回补)

Revision ID: b4c6d8e0f2a1
Revises: a3f5b2c9d8e7
Create Date: 2026-08-16 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'b4c6d8e0f2a1'
down_revision: Union[str, Sequence[str], None] = 'a3f5b2c9d8e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 可空列直接添加(存量数据 NULL=不限量,无需 server_default)
    op.add_column('dish', sa.Column('stock', mysql.INTEGER(display_width=11),
                                    nullable=True, comment='库存(份),NULL=不限量'))
    op.add_column('setmeal', sa.Column('stock', mysql.INTEGER(display_width=11),
                                       nullable=True, comment='库存(份),NULL=不限量'))
    # 回补幂等标志:NOT NULL 列需 server_default 处理存量行
    op.add_column('orders', sa.Column('stock_restored', mysql.INTEGER(display_width=11),
                                      nullable=False, server_default='0', comment='库存是否已回补 0否 1是'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('orders', 'stock_restored')
    op.drop_column('setmeal', 'stock')
    op.drop_column('dish', 'stock')
