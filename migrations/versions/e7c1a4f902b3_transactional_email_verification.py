"""transactional_email_verification

Revision ID: e7c1a4f902b3
Revises: a5614f0aef99
Create Date: 2026-09-22 19:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e7c1a4f902b3'
down_revision = 'a5614f0aef99'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.add_column(sa.Column('email_verified_at', sa.DateTime(), nullable=True))

    # Existing-user migration strategy (item 20): mandatory verification is a NEW requirement, introduced
    # today. Leaving every pre-existing customer's email_verified_at NULL would lock real, currently-active
    # customers out of My Account and every service workflow the moment this deploys — not acceptable.
    # Claiming they went through the 6-digit code flow at REGISTRATION time would be fabricated history —
    # also not acceptable. The honest middle ground: every account that already existed is grandfathered as
    # verified AS OF THIS MIGRATION (the true timestamp of this administrative action, not a fabricated past
    # date). Only accounts registered AFTER this migration runs go through the real verification flow.
    import datetime as _dt

    op.execute(
        sa.text("UPDATE students SET email_verified_at = :now WHERE email_verified_at IS NULL")
        .bindparams(now=_dt.datetime.utcnow())
    )

    op.create_table(
        'email_verification_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('purpose', sa.String(length=20), nullable=False),
        sa.Column('pending_email', sa.String(length=255), nullable=True),
        sa.Column('code_hash', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('attempts', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('consumed_at', sa.DateTime(), nullable=True),
        sa.Column('invalidated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name='fk_email_verification_codes_student'),
    )
    with op.batch_alter_table('email_verification_codes', schema=None) as batch_op:
        batch_op.create_index('ix_email_verification_codes_student_id', ['student_id'])

    op.create_table(
        'password_reset_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('token_hash', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('used_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name='fk_password_reset_tokens_student'),
    )
    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.create_index('ix_password_reset_tokens_student_id', ['student_id'])
        batch_op.create_index('ix_password_reset_tokens_token_hash', ['token_hash'])

    op.create_table(
        'email_logs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('student_id', sa.Integer(), nullable=True),
        sa.Column('recipient_email', sa.String(length=255), nullable=False),
        sa.Column('recipient_name', sa.String(length=200), nullable=True),
        sa.Column('template_key', sa.String(length=60), nullable=False),
        sa.Column('language', sa.String(length=2), nullable=False, server_default='en'),
        sa.Column('subject', sa.String(length=255), nullable=False),
        sa.Column('related_type', sa.String(length=40), nullable=True),
        sa.Column('related_id', sa.Integer(), nullable=True),
        sa.Column('ref_json', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_attempt_at', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('failed_at', sa.DateTime(), nullable=True),
        sa.Column('failure_reason', sa.String(length=500), nullable=True),
        sa.Column('dedupe_key', sa.String(length=160), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name='fk_email_logs_student'),
    )
    with op.batch_alter_table('email_logs', schema=None) as batch_op:
        batch_op.create_index('ix_email_logs_student_id', ['student_id'])
        batch_op.create_index('ix_email_logs_template_key', ['template_key'])
        batch_op.create_index('ix_email_logs_status', ['status'])
        batch_op.create_index('ix_email_logs_dedupe_key', ['dedupe_key'])


def downgrade():
    with op.batch_alter_table('email_logs', schema=None) as batch_op:
        batch_op.drop_index('ix_email_logs_dedupe_key')
        batch_op.drop_index('ix_email_logs_status')
        batch_op.drop_index('ix_email_logs_template_key')
        batch_op.drop_index('ix_email_logs_student_id')
    op.drop_table('email_logs')

    with op.batch_alter_table('password_reset_tokens', schema=None) as batch_op:
        batch_op.drop_index('ix_password_reset_tokens_token_hash')
        batch_op.drop_index('ix_password_reset_tokens_student_id')
    op.drop_table('password_reset_tokens')

    with op.batch_alter_table('email_verification_codes', schema=None) as batch_op:
        batch_op.drop_index('ix_email_verification_codes_student_id')
    op.drop_table('email_verification_codes')

    with op.batch_alter_table('students', schema=None) as batch_op:
        batch_op.drop_column('email_verified_at')
