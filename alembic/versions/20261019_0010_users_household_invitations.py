"""Add display names and household invitations."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision = "20261019_0010"
down_revision = "20261019_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "display_name" not in user_columns:
        op.add_column("users", sa.Column("display_name", sa.String(length=120), nullable=True))
        op.execute("UPDATE users SET display_name = username WHERE display_name IS NULL")
        op.alter_column("users", "display_name", nullable=False)
    if "household_invitations" not in inspector.get_table_names():
        op.create_table(
        "household_invitations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("household_id", sa.Integer(), sa.ForeignKey("households.id"), nullable=False),
        sa.Column("invited_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invited_by_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("role", sa.String(length=50), nullable=False, server_default="member"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("household_id", "invited_user_id", "status"),
        )
    indexes = {index["name"] for index in inspect(bind).get_indexes("household_invitations")}
    for name, columns in {
        "ix_household_invitations_household_id": ["household_id"],
        "ix_household_invitations_invited_user_id": ["invited_user_id"],
        "ix_household_invitations_status": ["status"],
    }.items():
        if name not in indexes:
            op.create_index(name, "household_invitations", columns)


def downgrade() -> None:
    op.drop_index("ix_household_invitations_status", table_name="household_invitations")
    op.drop_index("ix_household_invitations_invited_user_id", table_name="household_invitations")
    op.drop_index("ix_household_invitations_household_id", table_name="household_invitations")
    op.drop_table("household_invitations")
    op.drop_column("users", "display_name")
