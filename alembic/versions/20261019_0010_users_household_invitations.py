"""Add display names and household invitations."""

from alembic import op
import sqlalchemy as sa


revision = "20261019_0010"
down_revision = "20261019_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("display_name", sa.String(length=120), nullable=True))
    op.execute("UPDATE users SET display_name = username WHERE display_name IS NULL")
    op.alter_column("users", "display_name", nullable=False)
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
    op.create_index("ix_household_invitations_household_id", "household_invitations", ["household_id"])
    op.create_index("ix_household_invitations_invited_user_id", "household_invitations", ["invited_user_id"])
    op.create_index("ix_household_invitations_status", "household_invitations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_household_invitations_status", table_name="household_invitations")
    op.drop_index("ix_household_invitations_invited_user_id", table_name="household_invitations")
    op.drop_index("ix_household_invitations_household_id", table_name="household_invitations")
    op.drop_table("household_invitations")
    op.drop_column("users", "display_name")
