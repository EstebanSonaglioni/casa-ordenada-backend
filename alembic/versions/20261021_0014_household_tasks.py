"""Add household tasks and scheduled occurrences."""

from alembic import op
import sqlalchemy as sa

revision = "20261021_0014"
down_revision = "20261019_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "household_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.String(length=40), nullable=False, server_default="other"),
        sa.Column("difficulty", sa.String(length=20), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("estimated_amount_cents", sa.Integer(), nullable=True),
        sa.Column("currency_id", sa.Integer(), sa.ForeignKey("currencies.id"), nullable=True),
        sa.Column("assigned_to_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recurrence", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("recurrence_days", sa.String(length=20), nullable=True),
        sa.Column("recurrence_until", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_household_tasks_household_id", "household_tasks", ["household_id"])
    op.create_index("ix_household_tasks_assigned_to_user_id", "household_tasks", ["assigned_to_user_id"])
    op.create_index("ix_household_tasks_due_at", "household_tasks", ["due_at"])
    op.create_index("ix_household_tasks_recurrence", "household_tasks", ["recurrence"])
    op.create_index("ix_household_tasks_status", "household_tasks", ["status"])
    op.create_table(
        "household_task_occurrences",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("task_id", sa.Integer(), sa.ForeignKey("household_tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id"), nullable=False),
        sa.Column("occurrence_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("task_id", "occurrence_date"),
    )
    op.create_index("ix_household_task_occurrences_task_id", "household_task_occurrences", ["task_id"])
    op.create_index("ix_household_task_occurrences_household_id", "household_task_occurrences", ["household_id"])
    op.create_index("ix_household_task_occurrences_occurrence_date", "household_task_occurrences", ["occurrence_date"])
    op.create_index("ix_household_task_occurrences_status", "household_task_occurrences", ["status"])


def downgrade() -> None:
    op.drop_table("household_task_occurrences")
    op.drop_table("household_tasks")
