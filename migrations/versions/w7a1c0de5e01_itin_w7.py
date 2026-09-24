"""ITIN / Form W-7: case data, W-7 applications, document original tracking, passport extractions

Revision ID: w7a1c0de5e01
Revises: d260c0a51e02
Create Date: 2026-09-19 22:00:00

Additive only: four new tables. No existing table, row, application, case or person is changed.
"""
from alembic import op
import sqlalchemy as sa

revision = "w7a1c0de5e01"
down_revision = "d260c0a51e02"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "itin_case_data",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("case_id", sa.Integer(), nullable=False),
        sa.Column("tax_year", sa.Integer()),
        sa.Column("request_kind", sa.String(length=10)),
        sa.Column("preparing_return", sa.String(length=10)),
        sa.Column("taxpayer_us_status", sa.String(length=10)),
        sa.Column("stage", sa.String(length=20)),
        sa.Column("income_type", sa.String(length=20)),
        sa.Column("work_activity", sa.String(length=200)),
        sa.Column("occupation", sa.String(length=120)),
        sa.Column("gross_income", sa.String(length=30)),
        sa.Column("tax_return_ready_at", sa.DateTime()),
        sa.Column("w7_ready_at", sa.DateTime()),
        sa.Column("docs_ready_at", sa.DateTime()),
        sa.Column("ready_for_irs_at", sa.DateTime()),
        sa.Column("ready_for_irs_by", sa.String(length=120)),
        sa.Column("usps_tracking", sa.String(length=60)),
        sa.Column("irs_mailed_date", sa.Date()),
        sa.Column("irs_delivered_date", sa.Date()),
        sa.Column("irs_mailing_status", sa.String(length=120)),
        sa.Column("irs_outcome", sa.String(length=20)),
        sa.Column("irs_outcome_at", sa.Date()),
        sa.Column("irs_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("case_id"),
    )
    op.create_table(
        "w7_applications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("applicant_kind", sa.String(length=12), server_default="primary", nullable=False),
        sa.Column("application_type", sa.String(length=10)),
        sa.Column("reason_candidate", sa.String(length=40)),
        sa.Column("reason_confirmed", sa.String(length=4)),
        sa.Column("reason_confirmed_by", sa.String(length=120)),
        sa.Column("reason_confirmed_at", sa.DateTime()),
        sa.Column("reason_note", sa.Text()),
        sa.Column("signature_state", sa.String(length=16), server_default="not_started"),
        sa.Column("signature_note", sa.String(length=200)),
        sa.Column("caa_status", sa.String(length=12), server_default="not_reviewed"),
        sa.Column("caa_verified_by", sa.String(length=120)),
        sa.Column("caa_verified_at", sa.DateTime()),
        sa.Column("caa_note", sa.String(length=300)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["submission_id"], ["form_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id"),
    )
    op.create_table(
        "itin_doc_tracks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("requirement_id", sa.Integer(), nullable=False),
        sa.Column("doc_key", sa.String(length=30)),
        sa.Column("original_required", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("caa_route", sa.String(length=12)),
        sa.Column("original_state", sa.String(length=16), server_default="none"),
        sa.Column("delivery_choice", sa.String(length=10)),
        sa.Column("mailed_date", sa.Date()),
        sa.Column("inbound_tracking", sa.String(length=60)),
        sa.Column("received_date", sa.Date()),
        sa.Column("received_by", sa.String(length=120)),
        sa.Column("caa_verified_by", sa.String(length=120)),
        sa.Column("caa_verified_at", sa.DateTime()),
        sa.Column("caa_document_id", sa.Integer()),
        sa.Column("return_method", sa.String(length=20)),
        sa.Column("returned_date", sa.Date()),
        sa.Column("outbound_tracking", sa.String(length=60)),
        sa.Column("updated_at", sa.DateTime()),
        sa.ForeignKeyConstraint(["requirement_id"], ["case_document_requirements.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("requirement_id"),
    )
    op.create_table(
        "w7_extractions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer()),
        sa.Column("kind", sa.String(length=10)),
        sa.Column("source", sa.String(length=14)),
        sa.Column("values_json", sa.Text()),
        sa.Column("status", sa.String(length=12)),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("confirmed_at", sa.DateTime()),
        sa.Column("confirmed_by", sa.String(length=20)),
        sa.ForeignKeyConstraint(["document_id"], ["case_documents.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["form_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("w7_extractions", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_w7_extractions_submission_id"), ["submission_id"], unique=False)


def downgrade():
    op.drop_table("w7_extractions")
    op.drop_table("itin_doc_tracks")
    op.drop_table("w7_applications")
    op.drop_table("itin_case_data")
