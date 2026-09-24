"""field multi-form source mapping

Revision ID: 3b1a130a0001
Revises: 2a00ebffff38
Create Date: 2026-09-19 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '3b1a130a0001'
down_revision = '2a00ebffff38'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('form_fields', schema=None) as batch_op:
        batch_op.add_column(sa.Column('source_form', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('source_edition', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('source_extra_json', sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table('form_fields', schema=None) as batch_op:
        batch_op.drop_column('source_extra_json')
        batch_op.drop_column('source_edition')
        batch_op.drop_column('source_form')
