"""Add personal exercise tracking entries."""

from alembic import op
import sqlalchemy as sa

revision = "20261019_0008"
down_revision = "20261003_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.create_index("ix_exercise_entries_household_id", "exercise_entries", ["household_id"])
    op.create_index("ix_exercise_entries_user_id", "exercise_entries", ["user_id"])
    op.create_index("ix_exercise_entries_performed_on", "exercise_entries", ["performed_on"])


def downgrade() -> None:
    op.drop_table("exercise_entries")
