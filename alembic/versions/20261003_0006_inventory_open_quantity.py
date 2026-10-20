"""Track the opened quantity of inventory lots."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261003_0006"
down_revision = "20261003_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    columns = {column["name"] for column in inspect(bind).get_columns("inventory_items")}
    if "quantity_opened" not in columns:
        op.add_column(
            "inventory_items",
            sa.Column("quantity_opened", sa.Numeric(12, 3), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    pass
