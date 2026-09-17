"""assets

Revision ID: 96be783bb53e
Revises: fc1d3a92f7ec
"""

import sqlalchemy as sa
from alembic import op

revision = "96be783bb53e"
down_revision = "fc1d3a92f7ec"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "assets",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("source", sa.String(length=16), nullable=False),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("image_format", sa.String(length=8), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("has_alpha", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key"),
    )
    op.create_index(op.f("ix_assets_user_id"), "assets", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_assets_user_id"), table_name="assets")
    op.drop_table("assets")
