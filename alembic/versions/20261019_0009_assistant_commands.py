"""Add confirmed voice assistant command drafts."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = "20261019_0009"
down_revision = "20261019_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if "assistant_commands" not in inspect(bind).get_table_names():
        op.create_table(
        "assistant_commands",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("household_id", sa.Integer, sa.ForeignKey("households.id"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="awaiting_confirmation"),
        sa.Column("transcript", sa.Text, nullable=False),
        sa.Column("proposal", sa.JSON, nullable=False),
        sa.Column("audio_path", sa.String(500)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("confirmed_at", sa.DateTime(timezone=True)),
        )
    indexes = {index["name"] for index in inspect(bind).get_indexes("assistant_commands")}
    for name, columns in {
        "ix_assistant_commands_household_id": ["household_id"],
        "ix_assistant_commands_user_id": ["user_id"],
        "ix_assistant_commands_status": ["status"],
        "ix_assistant_commands_expires_at": ["expires_at"],
    }.items():
        if name not in indexes:
            op.create_index(name, "assistant_commands", columns)


def downgrade() -> None:
    op.drop_table("assistant_commands")
