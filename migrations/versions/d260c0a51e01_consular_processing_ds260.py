"""consular processing: DS-260 source snapshots, consular case data, DS-260 applications, CEAC-ready overrides

Revision ID: d260c0a51e01
Revises: b4d1e9a2c7f3
Create Date: 2026-09-19 18:00:00

Additive only: four new tables. No existing table, row, answer, application, case or person is changed.
"""
from alembic import op
import sqlalchemy as sa

revision = "d260c0a51e01"
down_revision = "b4d1e9a2c7f3"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "ds260_sources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("agency", sa.String(length=80), nullable=False),
        sa.Column("system", sa.String(length=40), nullable=False),
        sa.Column("form_name", sa.String(length=20), nullable=False),
        sa.Column("official_name", sa.String(length=200), nullable=False),
        sa.Column("source_label", sa.String(length=200), nullable=True),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column("sample_date", sa.String(length=20), nullable=True),
        sa.Column("verified_at", sa.Date(), nullable=True),
        sa.Column("schema_hash", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_current", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "consular_case_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("nvc_case_number", sa.String(length=40), nullable=True),
        sa.Column("invoice_id", sa.String(length=40), nullable=True),
        sa.Column("petition_type", sa.String(length=60), nullable=True),
        sa.Column("priority_date", sa.Date(), nullable=True),
        sa.Column("post", sa.String(length=120), nullable=True),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("visa_class", sa.String(length=20), nullable=True),
        sa.Column("nvc_status", sa.String(length=120), nullable=True),
        sa.Column("dq_date", sa.Date(), nullable=True),
        sa.Column("interview_date", sa.Date(), nullable=True),
        sa.Column("petitioner_person_id", sa.Integer(), nullable=True),
        sa.Column("underlying_submission_id", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.ForeignKeyConstraint(["petitioner_person_id"], ["persons.id"]),
        sa.ForeignKeyConstraint(["underlying_submission_id"], ["form_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
    )
    op.create_table(
        "ds260_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), nullable=True),
        sa.Column("applicant_role", sa.String(length=12), server_default="principal", nullable=False),
        sa.Column("ceac_status", sa.String(length=20), server_default="not_started", nullable=False),
        sa.Column("ceac_status_at", sa.DateTime(), nullable=True),
        sa.Column("ceac_status_by", sa.String(length=120), nullable=True),
        sa.Column("ceac_note", sa.Text(), nullable=True),
        sa.Column("ready_for_ceac_at", sa.DateTime(), nullable=True),
        sa.Column("ready_for_ceac_by", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["ds260_sources.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["form_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_table(
        "ds260_ceac_overrides",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("field_key", sa.String(length=80), nullable=False),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.String(length=120), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(["submission_id"], ["form_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id", "field_key", name="uq_ds260_override"),
    )
    with op.batch_alter_table("ds260_ceac_overrides", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_ds260_ceac_overrides_submission_id"), ["submission_id"], unique=False)


def downgrade():
    op.drop_table("ds260_ceac_overrides")
    op.drop_table("ds260_applications")
    op.drop_table("consular_case_data")
    op.drop_table("ds260_sources")
