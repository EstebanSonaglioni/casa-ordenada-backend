"""Add Mercado Pago external accounts, reserves, and movements."""

from alembic import op
import sqlalchemy as sa

revision = "20261003_0007"
down_revision = "20261003_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("external_accounts", sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("provider", sa.String(40), nullable=False), sa.Column("external_user_id", sa.String(120)), sa.Column("display_name", sa.String(120), nullable=False), sa.Column("active", sa.Boolean, nullable=False, server_default=sa.true()), sa.Column("last_synced_at", sa.DateTime(timezone=True)))
    op.create_table("external_reserves", sa.Column("id", sa.Integer, primary_key=True), sa.Column("account_id", sa.Integer, sa.ForeignKey("external_accounts.id"), nullable=False), sa.Column("external_id", sa.String(160), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("amount_cents", sa.Integer, nullable=False), sa.Column("currency_id", sa.Integer, sa.ForeignKey("currencies.id"), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="active"), sa.Column("raw_data", sa.JSON, nullable=False, server_default="{}"), sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("account_id", "external_id"))
    op.create_table("external_reserve_links", sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("category_id", sa.Integer, sa.ForeignKey("categories.id"), nullable=False), sa.Column("external_reserve_id", sa.Integer, sa.ForeignKey("external_reserves.id"), nullable=False), sa.Column("linked_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("category_id"), sa.UniqueConstraint("external_reserve_id"))
    op.create_table("external_movements", sa.Column("id", sa.Integer, primary_key=True), sa.Column("account_id", sa.Integer, sa.ForeignKey("external_accounts.id"), nullable=False), sa.Column("external_id", sa.String(160), nullable=False), sa.Column("movement_type", sa.String(40), nullable=False, server_default="payment"), sa.Column("direction", sa.String(10), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("amount_cents", sa.Integer, nullable=False), sa.Column("currency_id", sa.Integer, sa.ForeignKey("currencies.id"), nullable=False), sa.Column("description", sa.String(240), nullable=False), sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False), sa.Column("linked_expense_id", sa.Integer, sa.ForeignKey("expenses.id")), sa.Column("raw_data", sa.JSON, nullable=False, server_default="{}"), sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now()), sa.UniqueConstraint("account_id", "external_id"))


def downgrade() -> None:
    pass
