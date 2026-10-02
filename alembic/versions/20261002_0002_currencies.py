"""Add currencies, exchange rates, and monetary metadata."""

from alembic import op
from sqlalchemy import text

revision = "20261002_0002"
down_revision = "20261002_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(text("""
        CREATE TABLE IF NOT EXISTS currencies (
            id SERIAL PRIMARY KEY,
            code VARCHAR(3) NOT NULL UNIQUE,
            name VARCHAR(60) NOT NULL,
            symbol VARCHAR(5) NOT NULL,
            decimal_places INTEGER NOT NULL DEFAULT 2,
            is_active BOOLEAN NOT NULL DEFAULT TRUE
        )
    """))
    bind.execute(text("""
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id SERIAL PRIMARY KEY,
            base_currency_id INTEGER NOT NULL REFERENCES currencies(id),
            quote_currency_id INTEGER NOT NULL REFERENCES currencies(id),
            rate NUMERIC(20, 8) NOT NULL,
            effective_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """))
    for table in ("incomes", "recurring_expenses", "planned_expenses", "monthly_allocations", "expenses"):
        bind.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS currency_id INTEGER NOT NULL DEFAULT 1"))
    bind.execute(text("ALTER TABLE recurring_expenses ADD COLUMN IF NOT EXISTS due_date DATE"))
    bind.execute(text("UPDATE recurring_expenses SET due_date = make_date(2000, 1, due_day) WHERE due_date IS NULL"))


def downgrade() -> None:
    pass
