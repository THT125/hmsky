"""create coupon tables

优惠券:coupon(券模板)+ user_coupon(用户持有)。
user_coupon 唯一约束 uk_user_coupon(user_id,coupon_id) 为防超发数据库兜底。

Revision ID: d8e9f0a1b2c3
Revises: c7d9e8f0a1b2
Create Date: 2026-08-18 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'd8e9f0a1b2c3'
down_revision: Union[str, Sequence[str], None] = 'c7d9e8f0a1b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'coupon',
        sa.Column('id', mysql.BIGINT(display_width=20), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('name', mysql.VARCHAR(charset='utf8mb4', collation='utf8mb4_unicode_ci', length=50),
                  nullable=False, comment='券名称'),
        sa.Column('type', mysql.INTEGER(display_width=11), nullable=False, comment='类型 1满减 2折扣'),
        sa.Column('amount', mysql.DECIMAL(precision=10, scale=2), nullable=False,
                  comment='满减=减免金额;折扣=折扣率(如8.5=85折)'),
        sa.Column('min_amount', mysql.DECIMAL(precision=10, scale=2), nullable=False, server_default='0',
                  comment='使用门槛(满X可用,0=无门槛)'),
        sa.Column('total', mysql.INTEGER(display_width=11), nullable=False, comment='发放总量'),
        sa.Column('stock', mysql.INTEGER(display_width=11), nullable=False, comment='剩余量(初始=total,抢券扣减)'),
        sa.Column('per_user_limit', mysql.INTEGER(display_width=11), nullable=False, server_default='1',
                  comment='每人限领'),
        sa.Column('start_time', mysql.DATETIME(), nullable=False, comment='可领开始时间'),
        sa.Column('end_time', mysql.DATETIME(), nullable=False, comment='可领结束时间'),
        sa.Column('status', mysql.INTEGER(display_width=11), nullable=False, server_default='1',
                  comment='状态 0停用 1启用'),
        sa.Column('create_time', mysql.DATETIME(), nullable=True, comment='创建时间'),
        sa.Column('update_time', mysql.DATETIME(), nullable=True, comment='更新时间'),
        sa.Column('create_user', mysql.BIGINT(display_width=20), nullable=True, comment='创建人'),
        sa.Column('update_user', mysql.BIGINT(display_width=20), nullable=True, comment='修改人'),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_unicode_ci',
        mysql_default_charset='utf8mb4',
        comment='优惠券模板',
    )
    op.create_table(
        'user_coupon',
        sa.Column('id', mysql.BIGINT(display_width=20), autoincrement=True, nullable=False, comment='主键'),
        sa.Column('user_id', mysql.BIGINT(display_width=20), nullable=False, comment='用户id'),
        sa.Column('coupon_id', mysql.BIGINT(display_width=20), nullable=False, comment='券模板id'),
        sa.Column('status', mysql.INTEGER(display_width=11), nullable=False, server_default='0',
                  comment='状态 0未用 1已用 2过期'),
        sa.Column('order_id', mysql.BIGINT(display_width=20), nullable=True, comment='使用订单id(下期抵扣用)'),
        sa.Column('use_time', mysql.DATETIME(), nullable=True, comment='使用时间'),
        sa.Column('create_time', mysql.DATETIME(), nullable=True, comment='领取时间'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'coupon_id', name='uk_user_coupon'),
        mysql_collate='utf8mb4_unicode_ci',
        mysql_default_charset='utf8mb4',
        comment='用户优惠券',
    )
    op.create_index('idx_user_coupon_user', 'user_coupon', ['user_id', 'status'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_user_coupon_user', table_name='user_coupon')
    op.drop_table('user_coupon')
    op.drop_table('coupon')
