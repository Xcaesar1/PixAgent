"""history seq

Revision ID: fa850313b768
Revises: 76210ee84e61
"""

import sqlalchemy as sa
from alembic import op

revision = "fa850313b768"
down_revision = "76210ee84e61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "edit_sessions",
        sa.Column("history_seq", sa.Integer(), nullable=False, server_default="1"),
    )
    op.execute(
        """
        UPDATE edit_sessions AS sessions
        SET history_seq = COALESCE(
            (SELECT MAX(seq) FROM edit_history WHERE session_id = sessions.id),
            1
        )
        """
    )
    op.alter_column("edit_sessions", "history_seq", server_default=None)


def downgrade() -> None:
    op.drop_column("edit_sessions", "history_seq")
