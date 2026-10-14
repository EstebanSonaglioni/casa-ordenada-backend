"""Create inventory, shopping, and purchase tables."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261003_0004"
down_revision = "20261002_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(inspect(bind).get_table_names())
    tables = {
        "inventory_categories": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("color", sa.String(7)), sa.UniqueConstraint("household_id", "name")],
        "storage_locations": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("kind", sa.String(30), nullable=False, server_default="other"), sa.UniqueConstraint("household_id", "name")],
        "products": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("inventory_category_id", sa.Integer, sa.ForeignKey("inventory_categories.id"), nullable=False), sa.Column("name", sa.String(160), nullable=False), sa.Column("brand", sa.String(100), nullable=False, server_default=""), sa.Column("default_unit", sa.String(20), nullable=False, server_default="unit"), sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()), sa.UniqueConstraint("household_id", "name", "brand")],
        "shopping_lists": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("name", sa.String(120), nullable=False, server_default="Compras pendientes"), sa.Column("status", sa.String(20), nullable=False, server_default="active"), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now())],
        "shopping_items": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("shopping_list_id", sa.Integer, sa.ForeignKey("shopping_lists.id"), nullable=False), sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id")), sa.Column("requested_name", sa.String(160), nullable=False), sa.Column("quantity_requested", sa.Numeric(12, 3), nullable=False, server_default="1"), sa.Column("quantity_remaining", sa.Numeric(12, 3), nullable=False, server_default="1"), sa.Column("unit", sa.String(20), nullable=False, server_default="unit"), sa.Column("priority", sa.String(20), nullable=False, server_default="normal"), sa.Column("status", sa.String(20), nullable=False, server_default="pending"), sa.Column("note", sa.Text)],
        "purchases": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("shopping_list_id", sa.Integer, sa.ForeignKey("shopping_lists.id")), sa.Column("expense_id", sa.Integer, sa.ForeignKey("expenses.id"), nullable=False, unique=True), sa.Column("purchased_on", sa.Date, nullable=False), sa.Column("store", sa.String(120)), sa.Column("currency_id", sa.Integer, sa.ForeignKey("currencies.id"), nullable=False), sa.Column("total_amount_cents", sa.Integer, nullable=False)],
        "purchase_items": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("purchase_id", sa.Integer, sa.ForeignKey("purchases.id", ondelete="CASCADE"), nullable=False), sa.Column("shopping_item_id", sa.Integer, sa.ForeignKey("shopping_items.id")), sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False), sa.Column("exact_name", sa.String(160), nullable=False), sa.Column("quantity", sa.Numeric(12, 3), nullable=False), sa.Column("unit", sa.String(20), nullable=False), sa.Column("unit_price_cents", sa.Integer, nullable=False), sa.Column("total_price_cents", sa.Integer, nullable=False), sa.Column("expires_on", sa.Date), sa.Column("storage_location_id", sa.Integer, sa.ForeignKey("storage_locations.id"), nullable=False)],
        "inventory_items": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False), sa.Column("product_id", sa.Integer, sa.ForeignKey("products.id"), nullable=False), sa.Column("storage_location_id", sa.Integer, sa.ForeignKey("storage_locations.id"), nullable=False), sa.Column("purchase_item_id", sa.Integer, sa.ForeignKey("purchase_items.id")), sa.Column("quantity_initial", sa.Numeric(12, 3), nullable=False), sa.Column("quantity_remaining", sa.Numeric(12, 3), nullable=False), sa.Column("unit", sa.String(20), nullable=False), sa.Column("purchased_on", sa.Date, nullable=False), sa.Column("expires_on", sa.Date), sa.Column("opened_on", sa.Date), sa.Column("status", sa.String(20), nullable=False, server_default="closed"), sa.Column("notes", sa.Text)],
        "inventory_movements": [sa.Column("id", sa.Integer, primary_key=True), sa.Column("inventory_item_id", sa.Integer, sa.ForeignKey("inventory_items.id"), nullable=False), sa.Column("type", sa.String(20), nullable=False), sa.Column("quantity", sa.Numeric(12, 3), nullable=False), sa.Column("occurred_on", sa.Date, nullable=False), sa.Column("note", sa.Text), sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=False)],
    }
    for name, columns in tables.items():
        if name not in existing:
            op.create_table(name, *columns)


def downgrade() -> None:
    pass
