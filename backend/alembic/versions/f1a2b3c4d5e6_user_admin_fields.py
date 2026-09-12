"""user admin fields

用户管理模块:
- user 加 status(封禁)/ ban_reason / last_login_time / last_login_ip / update_time / update_user
  封禁是"禁登录 + 即时踢下线 + 禁止下单",不做物理删除(订单/优惠券有关联)
- user_login_log 加两个索引:风控按 user_id 聚合 IP 分散度、按 ip 聚合多账号,
  没有索引会全表扫;同时支撑详情页登录日志分页

Revision ID: f1a2b3c4d5e6
Revises: e0f1a2b3c4d5
Create Date: 2026-09-12 17:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e0f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 可空列直接添加(存量行为 NULL,无需 server_default)
    op.add_column('user', sa.Column('ban_reason', sa.String(length=255),
                                    nullable=True, comment='封禁原因(审计)'))
    op.add_column('user', sa.Column('last_login_time', mysql.DATETIME(),
                                    nullable=True, comment='最近登录时间'))
    op.add_column('user', sa.Column('last_login_ip', sa.String(length=50),
                                    nullable=True, comment='最近登录IP'))
    op.add_column('user', sa.Column('update_time', mysql.DATETIME(),
                                    nullable=True, comment='更新时间'))
    op.add_column('user', sa.Column('update_user', mysql.BIGINT(),
                                    nullable=True, comment='最后操作人(管理端员工id)'))
    # NOT NULL 列需 server_default 处理存量行(存量用户一律置为正常)
    op.add_column('user', sa.Column('status', mysql.INTEGER(display_width=11), nullable=False,
                                    server_default='1', comment='1正常 0封禁'))

    # 风控分析 + 登录日志分页的性能前提
    op.create_index('idx_ull_user_time', 'user_login_log', ['user_id', 'create_time'])
    op.create_index('idx_ull_ip_time', 'user_login_log', ['ip', 'create_time'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_ull_ip_time', table_name='user_login_log')
    op.drop_index('idx_ull_user_time', table_name='user_login_log')
    op.drop_column('user', 'status')
    op.drop_column('user', 'update_user')
    op.drop_column('user', 'update_time')
    op.drop_column('user', 'last_login_ip')
    op.drop_column('user', 'last_login_time')
    op.drop_column('user', 'ban_reason')
