"""consent to travel authorization for minors

Revision ID: 099a46eb3874
Revises: 78ebb2719c02
Create Date: 2026-09-24 18:00:00.000000

Additive only — new tables for the Consent to Travel Authorization for Minors Smart Intake (its own
`Case.case_type == "consent_travel"` on the existing Case + real-Person architecture). No existing table
is touched. Reuses `terms_acceptances` (terms_key="consent_travel") — no new terms table needed.

  consent_travel_case_data   one row per case: interview answers, workflow status, price/payment state.
  consent_travel_records     children (kind="child") and auto-synced consenting adults (kind="adult"),
                              each linked to a real Person via case_people.
  consent_travel_price_rules DATA-DRIVEN pricing (base document fee, additional-child fee). Admin-edited.
  consent_travel_quotes      every price the case ever had (system estimate + OG's confirmed total).
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '099a46eb3874'
down_revision = '78ebb2719c02'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'consent_travel_case_data',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('case_id', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=16), nullable=False, server_default='draft'),
        sa.Column('language', sa.String(length=2), nullable=True),
        sa.Column('answers_json', sa.Text(), nullable=True),
        sa.Column('doc_choices_json', sa.Text(), nullable=True),
        sa.Column('current_step', sa.String(length=40), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('reopened_at', sa.DateTime(), nullable=True),
        sa.Column('reopen_message', sa.Text(), nullable=True),
        sa.Column('resubmit_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('terms_id', sa.Integer(), nullable=True),
        sa.Column('customer_message', sa.Text(), nullable=True),
        sa.Column('approved_at', sa.DateTime(), nullable=True),
        sa.Column('approved_by_admin_id', sa.Integer(), nullable=True),
        sa.Column('price_status', sa.String(length=12), nullable=False, server_default='none'),
        sa.Column('payment_status', sa.String(length=12), nullable=False, server_default='not_started'),
        sa.Column('payment_reference', sa.String(length=80), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['case_id'], ['cases.id'], name='fk_ct_case'),
        sa.ForeignKeyConstraint(['terms_id'], ['terms_acceptances.id'], name='fk_ct_terms'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('case_id', name='uq_ct_case_id'),
    )
    op.create_table(
        'consent_travel_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ct_case_id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(length=16), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('data_json', sa.Text(), nullable=True),
        sa.Column('complete', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['ct_case_id'], ['consent_travel_case_data.id'], name='fk_ct_record_case'),
        sa.ForeignKeyConstraint(['person_id'], ['case_people.id'], name='fk_ct_record_person'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_consent_travel_records_ct_case_id', 'consent_travel_records', ['ct_case_id'])
    op.create_table(
        'consent_travel_price_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=40), nullable=False),
        sa.Column('label_en', sa.String(length=160), nullable=False),
        sa.Column('label_es', sa.String(length=160), nullable=False),
        sa.Column('amount_cents', sa.Integer(), nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('updated_by', sa.String(length=120), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code', name='uq_ct_price_rule_code'),
    )
    op.create_table(
        'consent_travel_quotes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ct_case_id', sa.Integer(), nullable=False),
        sa.Column('revision', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('source', sa.String(length=8), nullable=False, server_default='system'),
        sa.Column('lines_json', sa.Text(), nullable=True),
        sa.Column('system_estimate_cents', sa.Integer(), nullable=True),
        sa.Column('final_total_cents', sa.Integer(), nullable=True),
        sa.Column('previous_total_cents', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='estimated'),
        sa.Column('reason', sa.String(length=400), nullable=True),
        sa.Column('staff', sa.String(length=120), nullable=True),
        sa.Column('needs_ack', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['ct_case_id'], ['consent_travel_case_data.id'], name='fk_ct_quote_case'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_consent_travel_quotes_ct_case_id', 'consent_travel_quotes', ['ct_case_id'])


def downgrade():
    op.drop_index('ix_consent_travel_quotes_ct_case_id', table_name='consent_travel_quotes')
    op.drop_table('consent_travel_quotes')
    op.drop_table('consent_travel_price_rules')
    op.drop_index('ix_consent_travel_records_ct_case_id', table_name='consent_travel_records')
    op.drop_table('consent_travel_records')
    op.drop_table('consent_travel_case_data')
