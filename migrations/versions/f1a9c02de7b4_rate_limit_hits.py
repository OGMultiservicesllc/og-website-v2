"""rate_limit_hits

Revision ID: f1a9c02de7b4
Revises: e7c1a4f902b3
Create Date: 2026-09-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f1a9c02de7b4'
down_revision = 'e7c1a4f902b3'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'rate_limit_hits',
        sa.Column('key', sa.String(length=200), nullable=False),
        sa.Column('window_start', sa.Float(), nullable=False),
        sa.Column('hit_count', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('key', name='pk_rate_limit_hits'),
    )


def downgrade():
    op.drop_table('rate_limit_hits')
