"""widen dl_case_data.rules_version

Revision ID: 78ebb2719c02
Revises: 8b3bd7e6bbd8
Create Date: 2026-09-24 16:20:00.000000

Bug found live on staging (2026-09-24): `dl_case_data.rules_version` was `VARCHAR(20)`, but
`app.driver_license.rules.RULES_VERSION` is a "unverified-YYYY-MM-DD" string (22 characters) — every attempt to
save a NJ Driver License submission raised `psycopg2.errors.StringDataRightTruncation` and the customer-facing
POST to /nj-driver-license/send failed with a 500.

The column is widened to VARCHAR(64), not just enough to fit today's exact string, so a future RULES_VERSION
format change (e.g. "verified-by-og-2026-10-01", or a semantic version with a longer label) doesn't need another
migration for the same reason. Purely additive — no data is transformed; existing rows (if any ever wrote a
truncated/failed value, which they couldn't given the prior hard DB error) are untouched.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '78ebb2719c02'
down_revision = '8b3bd7e6bbd8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('dl_case_data', schema=None) as batch_op:
        batch_op.alter_column('rules_version',
                               existing_type=sa.String(length=20),
                               type_=sa.String(length=64),
                               existing_nullable=True)


def downgrade():
    with op.batch_alter_table('dl_case_data', schema=None) as batch_op:
        batch_op.alter_column('rules_version',
                               existing_type=sa.String(length=64),
                               type_=sa.String(length=20),
                               existing_nullable=True)
