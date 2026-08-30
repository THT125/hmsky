"""coupon valid_days + user_coupon expire_time

优惠券有效期:券模板加"有效天数"(领取后N天有效),用户持有券落库时计算过期时间。

Revision ID: e0f1a2b3c4d5
Revises: d8e9f0a1b2c3
Create Date: 2026-08-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'e0f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'd8e9f0a1b2c3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('coupon', sa.Column('valid_days', mysql.INTEGER(display_width=11),
                                      nullable=False, server_default='7',
                                      comment='有效天数(领取后N天内有效)'))
    op.add_column('user_coupon', sa.Column('expire_time', mysql.DATETIME(),
                                           nullable=True, comment='过期时间(领取时=领取时间+有效天数)'))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_coupon', 'expire_time')
    op.drop_column('coupon', 'valid_days')
