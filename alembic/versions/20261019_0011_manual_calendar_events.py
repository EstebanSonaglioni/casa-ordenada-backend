"""Add manual household calendar events."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261019_0011"
down_revision = "20261019_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "manual_calendar_events" not in inspect(bind).get_table_names():
        op.create_table(
        "manual_calendar_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id"), nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False, server_default="other"),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if "ix_manual_calendar_events_household_id" not in {index["name"] for index in inspect(bind).get_indexes("manual_calendar_events")}: 
        op.create_index("ix_manual_calendar_events_household_id", "manual_calendar_events", ["household_id"])


def downgrade() -> None:
    op.drop_index("ix_manual_calendar_events_household_id", table_name="manual_calendar_events")
    op.drop_table("manual_calendar_events")
