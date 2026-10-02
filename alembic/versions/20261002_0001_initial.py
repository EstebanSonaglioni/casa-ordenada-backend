"""Create the initial household finance schema."""

from alembic import op
from sqlalchemy import text

from app.database import Base
from app import finance_models, models  # noqa: F401

revision = "20261002_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    bind.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(50) NOT NULL DEFAULT 'member'"))


def downgrade() -> None:
    pass
