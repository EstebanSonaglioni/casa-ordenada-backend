"""Track recurring payments by due date."""

from alembic import op
from sqlalchemy import text

revision = "20261002_0003"
down_revision = "20261002_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.get_bind().execute(text("""
        CREATE TABLE IF NOT EXISTS recurring_payments (
            id SERIAL PRIMARY KEY,
            recurring_expense_id INTEGER NOT NULL REFERENCES recurring_expenses(id),
            due_date DATE NOT NULL,
            paid_on DATE NOT NULL,
            UNIQUE (recurring_expense_id, due_date)
        )
    """))


def downgrade() -> None:
    pass
