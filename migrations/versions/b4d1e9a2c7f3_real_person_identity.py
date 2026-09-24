"""real person identity above CasePerson, fact ownership by Person, fact claims

Revision ID: b4d1e9a2c7f3
Revises: a7972377f4aa
Create Date: 2026-09-19 14:00:00

Additive only: new `persons` and `case_person_fact_claims` tables, nullable `case_people.person_id` and
`case_person_facts.real_person_id`. `case_person_facts.person_id` becomes nullable (it is now only the CasePerson a
fact was first recorded through). Existing rows are linked/merged by the idempotent startup service
`cases.backfill_persons()` (never by name matching alone); no existing answer, application, case or person row is deleted.
"""
from alembic import op
import sqlalchemy as sa

revision = "b4d1e9a2c7f3"
down_revision = "a7972377f4aa"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "persons",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("is_self", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("given_name", sa.String(length=120), nullable=True),
        sa.Column("family_name", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["customer_id"], ["students.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("persons", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_persons_customer_id"), ["customer_id"], unique=False)
        # Partial unique index: at most one is_self=True Person per customer. `sqlite_where` and
        # `postgresql_where` are both required — each dialect only honors its OWN kwarg; without
        # `postgresql_where`, PostgreSQL silently drops the WHERE clause and this becomes a full unique
        # constraint on customer_id alone (at most ONE Person per customer, period — breaking every
        # multi-person case). Fixed 2026-09-23, Production Launch Readiness Audit finding E2. This
        # migration has never been run against PostgreSQL (no production deployment exists yet), so the
        # fix is made directly here rather than as a separate corrective migration.
        batch_op.create_index(
            "uq_person_self", ["customer_id"], unique=True,
            sqlite_where=sa.text("is_self = 1"),
            postgresql_where=sa.text("is_self = true"),
        )

    op.create_table(
        "case_person_fact_claims",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("fact_id", sa.Integer(), nullable=False),
        sa.Column("submission_id", sa.Integer(), nullable=True),
        sa.Column("source_form", sa.String(length=20), nullable=True),
        sa.Column("source_field", sa.String(length=100), nullable=True),
        sa.Column("source_ref", sa.String(length=120), nullable=True),
        sa.Column("value_json", sa.Text(), nullable=True),
        sa.Column("state", sa.String(length=12), server_default="draft", nullable=False),
        sa.Column("resolved", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("recorded_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["fact_id"], ["case_person_facts.id"]),
        sa.ForeignKeyConstraint(["submission_id"], ["form_submissions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fact_id", "submission_id", name="uq_fact_claim"),
    )
    with op.batch_alter_table("case_person_fact_claims", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_case_person_fact_claims_fact_id"), ["fact_id"], unique=False)
        batch_op.create_index(batch_op.f("ix_case_person_fact_claims_submission_id"), ["submission_id"], unique=False)

    with op.batch_alter_table("case_people", schema=None) as batch_op:
        batch_op.add_column(sa.Column("person_id", sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f("ix_case_people_person_id"), ["person_id"], unique=False)
        batch_op.create_foreign_key("fk_case_people_person", "persons", ["person_id"], ["id"])

    with op.batch_alter_table("case_person_facts", schema=None) as batch_op:
        batch_op.add_column(sa.Column("real_person_id", sa.Integer(), nullable=True))
        batch_op.alter_column("person_id", existing_type=sa.Integer(), nullable=True)
        batch_op.create_index(batch_op.f("ix_case_person_facts_real_person_id"), ["real_person_id"], unique=False)
        batch_op.create_foreign_key("fk_person_fact_owner", "persons", ["real_person_id"], ["id"])
        batch_op.create_unique_constraint("uq_person_fact_owner", ["real_person_id", "fact_key"])


def downgrade():
    with op.batch_alter_table("case_person_facts", schema=None) as batch_op:
        batch_op.drop_constraint("uq_person_fact_owner", type_="unique")
        batch_op.drop_constraint("fk_person_fact_owner", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_case_person_facts_real_person_id"))
        batch_op.drop_column("real_person_id")
    with op.batch_alter_table("case_people", schema=None) as batch_op:
        batch_op.drop_constraint("fk_case_people_person", type_="foreignkey")
        batch_op.drop_index(batch_op.f("ix_case_people_person_id"))
        batch_op.drop_column("person_id")
    op.drop_table("case_person_fact_claims")
    op.drop_table("persons")
