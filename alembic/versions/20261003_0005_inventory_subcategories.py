"""Add inventory subcategories, category icons, and purchase updates."""

from alembic import op
import sqlalchemy as sa

revision = "20261003_0005"
down_revision = "20261003_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("inventory_categories", sa.Column("icon", sa.String(30), nullable=False, server_default="other"))
    op.create_table("inventory_subcategories", sa.Column("id", sa.Integer, primary_key=True), sa.Column("inventory_category_id", sa.Integer, sa.ForeignKey("inventory_categories.id"), nullable=False), sa.Column("name", sa.String(100), nullable=False), sa.Column("icon", sa.String(30), nullable=False, server_default="other"), sa.UniqueConstraint("inventory_category_id", "name"))
    op.add_column("products", sa.Column("inventory_subcategory_id", sa.Integer, sa.ForeignKey("inventory_subcategories.id"), nullable=True))
    op.add_column("purchases", sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()))
    op.execute("UPDATE inventory_categories SET icon = CASE name WHEN 'Alimentos' THEN 'food' WHEN 'Limpieza' THEN 'clean' WHEN 'Higiene' THEN 'hygiene' WHEN 'Bebé' THEN 'baby' WHEN 'Farmacia' THEN 'medicine' ELSE 'other' END")


def downgrade() -> None:
    pass
