"""Tax Return case layer: tax case data, records, price rules and quotes, terms acceptances, bank info; cross-case document reuse column

Revision ID: tx25a1c0de01
Revises: w7a1c0de5e01
Create Date: 2026-09-20 18:00:00

Additive only: new tables, and ONE nullable column on case_documents. No existing row, case, application or person is changed.
"""
from alembic import op
import sqlalchemy as sa

revision = "tx25a1c0de01"
down_revision = "w7a1c0de5e01"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "terms_acceptances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer()),
        sa.Column("terms_key", sa.String(length=30), nullable=False),
        sa.Column("version", sa.String(length=30), nullable=False),
        sa.Column("language", sa.String(length=2)),
        sa.Column("certification_accepted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("terms_accepted", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("accepted_at", sa.DateTime(), nullable=False),
        sa.Column("ip_hash", sa.String(length=64)),
        sa.Column("user_agent", sa.String(length=200)),
        sa.ForeignKeyConstraint(["customer_id"], ["students.id"]),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_terms_acceptances_customer_id", "terms_acceptances", ["customer_id"])
    op.create_index("ix_terms_acceptances_case_id", "terms_acceptances", ["case_id"])
    op.create_table(
        "tax_case_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="draft"),
        sa.Column("language", sa.String(length=2)),
        sa.Column("is_returning", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("answers_json", sa.Text()),
        sa.Column("doc_choices_json", sa.Text()),
        sa.Column("current_step", sa.String(length=40)),
        sa.Column("submitted_at", sa.DateTime()),
        sa.Column("reopened_at", sa.DateTime()),
        sa.Column("reopen_message", sa.Text()),
        sa.Column("resubmit_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("terms_id", sa.Integer()),
        sa.Column("customer_message", sa.Text()),
        sa.Column("price_status", sa.String(length=12), nullable=False, server_default="none"),
        sa.Column("payment_status", sa.String(length=12), nullable=False, server_default="not_started"),
        sa.Column("payment_reference", sa.String(length=80)),
        sa.Column("filed_at", sa.Date()),
        sa.Column("accepted_at", sa.Date()),
        sa.Column("filing_note", sa.String(length=300)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["terms_id"], ["terms_acceptances.id"], name="fk_tax_terms"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
    )
    op.create_table(
        "tax_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tax_case_id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("person_id", sa.Integer()),
        sa.Column("data_json", sa.Text()),
        sa.Column("complete", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["tax_case_id"], ["tax_case_data.id"]),
        sa.ForeignKeyConstraint(["person_id"], ["case_people.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tax_records_tax_case_id", "tax_records", ["tax_case_id"])
    op.create_table(
        "tax_price_rules",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tax_year", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False),
        sa.Column("label_en", sa.String(length=160), nullable=False),
        sa.Column("label_es", sa.String(length=160), nullable=False),
        sa.Column("amount_cents", sa.Integer()),
        sa.Column("percent", sa.Float()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("params_json", sa.Text()),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column("updated_by", sa.String(length=120)),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tax_year", "code", name="uq_tax_price_rule"),
    )
    op.create_index("ix_tax_price_rules_tax_year", "tax_price_rules", ["tax_year"])
    op.create_table(
        "tax_price_quotes",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tax_case_id", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(length=8), nullable=False),
        sa.Column("mode", sa.String(length=8), nullable=False),
        sa.Column("category", sa.String(length=16)),
        sa.Column("lines_json", sa.Text()),
        sa.Column("system_estimate_cents", sa.Integer()),
        sa.Column("discount_percent", sa.Float()),
        sa.Column("discount_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_final_cents", sa.Integer()),
        sa.Column("final_fee_cents", sa.Integer()),
        sa.Column("previous_fee_cents", sa.Integer()),
        sa.Column("status", sa.String(length=12), nullable=False),
        sa.Column("reason", sa.String(length=400)),
        sa.Column("staff", sa.String(length=120)),
        sa.Column("config_json", sa.Text()),
        sa.Column("flags_json", sa.Text()),
        sa.Column("needs_ack", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("acknowledged_at", sa.DateTime()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tax_case_id"], ["tax_case_data.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_tax_price_quotes_tax_case_id", "tax_price_quotes", ["tax_case_id"])
    op.create_table(
        "tax_bank_info",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tax_case_id", sa.Integer(), nullable=False),
        sa.Column("account_type", sa.String(length=10)),
        sa.Column("routing_enc", sa.Text()),
        sa.Column("account_enc", sa.Text()),
        sa.Column("routing_last4", sa.String(length=4)),
        sa.Column("account_last4", sa.String(length=4)),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["tax_case_id"], ["tax_case_data.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tax_case_id"),
    )
    with op.batch_alter_table("case_documents") as batch:
        batch.add_column(sa.Column("reused_from_id", sa.Integer()))


def downgrade():
    with op.batch_alter_table("case_documents") as batch:
        batch.drop_column("reused_from_id")
    op.drop_table("tax_bank_info")
    op.drop_table("tax_price_quotes")
    op.drop_table("tax_price_rules")
    op.drop_table("tax_records")
    op.drop_table("tax_case_data")
    op.drop_table("terms_acceptances")
