"""alternate checkout payment methods: payment cancellation audit + cash app tag setting

Revision ID: 8b3bd7e6bbd8
Revises: b263d7c3e69e
Create Date: 2026-09-23 16:09:39.051278

Additive, for the Zelle / Cash App / Pay at Office alternate checkout methods added alongside the existing
Square flow (2026-09-23). No existing table, column, or Square-related data is touched.

  payments.canceled_at / canceled_by_admin_id — audit trail for Admin's new "Cancel / Reject Payment
  Request" action on a pending manual-method Payment. Mirrors the exact same shape charges.canceled_at and
  payment_requests.canceled_at/canceled_by_admin_id already use for their own cancellation, so this is
  consistent with the existing OG Payments audit pattern, not a new one.

  site_settings.cash_app_tag — optional override for the Cash App cashtag shown to customers at checkout;
  empty means "use app.business_info.CASH_APP_TAG_DEFAULT", the same "empty field = built-in default"
  convention PageBlock already uses. Not a secret (the cashtag is public information shown on the
  checkout page), so it needs no encryption/masking, same as every other SiteSettings field.

No new payment method value required a schema change: `payments.method` has always been a plain
VARCHAR(20) with no DB-level CHECK constraint (the allowed set — now including "cash_app" — is enforced in
Python via app.models.payments.PAYMENT_METHODS/MANUAL_METHODS), so adding "cash_app" was a code-only change.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '8b3bd7e6bbd8'
down_revision = 'b263d7c3e69e'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.add_column(sa.Column('canceled_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('canceled_by_admin_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_payments_canceled_by_admin', 'admin_users', ['canceled_by_admin_id'], ['id'])

    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('cash_app_tag', sa.String(length=60), nullable=True))


def downgrade():
    with op.batch_alter_table('site_settings', schema=None) as batch_op:
        batch_op.drop_column('cash_app_tag')

    with op.batch_alter_table('payments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_payments_canceled_by_admin', type_='foreignkey')
        batch_op.drop_column('canceled_by_admin_id')
        batch_op.drop_column('canceled_at')
