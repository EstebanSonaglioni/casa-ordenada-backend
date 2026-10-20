"""Add personal exercise tracking entries."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261019_0008"
down_revision = "20261003_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "exercise_entries" not in inspect(bind).get_table_names():
        op.create_table(
        "exercise_entries",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("performed_on", sa.Date, nullable=False),
        sa.Column("activity", sa.String(100), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        )
    indexes = {index["name"] for index in inspect(bind).get_indexes("exercise_entries")}
    for name, columns in {
        "ix_exercise_entries_household_id": ["household_id"],
        "ix_exercise_entries_user_id": ["user_id"],
        "ix_exercise_entries_performed_on": ["performed_on"],
    }.items():
        if name not in indexes:
            op.create_index(name, "exercise_entries", columns)


def downgrade() -> None:
    op.drop_table("exercise_entries")
