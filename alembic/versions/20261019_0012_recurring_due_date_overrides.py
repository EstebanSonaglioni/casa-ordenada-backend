"""Add per-month recurring due date overrides."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261019_0012"
down_revision = "20261019_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "recurring_due_date_overrides" not in inspect(bind).get_table_names():
        op.create_table(
        "recurring_due_date_overrides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recurring_expense_id", sa.Integer(), sa.ForeignKey("recurring_expenses.id", ondelete="CASCADE"), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("month", sa.Integer(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.UniqueConstraint("recurring_expense_id", "year", "month"),
        )
    if "ix_recurring_due_date_overrides_recurring_expense_id" not in {index["name"] for index in inspect(bind).get_indexes("recurring_due_date_overrides")}: 
        op.create_index("ix_recurring_due_date_overrides_recurring_expense_id", "recurring_due_date_overrides", ["recurring_expense_id"])


def downgrade() -> None:
    op.drop_index("ix_recurring_due_date_overrides_recurring_expense_id", table_name="recurring_due_date_overrides")
    op.drop_table("recurring_due_date_overrides")
