"""Make planned expense categories optional and add tags."""

from alembic import op
import sqlalchemy as sa

revision = "20261019_0013"
down_revision = "20261019_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column("planned_expenses", "category_id", nullable=True)
    op.add_column("planned_expenses", sa.Column("tags", sa.Text(), nullable=False, server_default=""))


def downgrade() -> None:
    op.drop_column("planned_expenses", "tags")
    op.alter_column("planned_expenses", "category_id", nullable=False)
