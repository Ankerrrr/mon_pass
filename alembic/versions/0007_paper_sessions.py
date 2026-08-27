"""paper trading sessions

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "paper_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("configuration_id", sa.Uuid(), nullable=True),
        sa.Column("configuration_version", sa.Integer(), nullable=False),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column("state_snapshot", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("connection_state", sa.String(16), nullable=False),
        sa.Column("last_candle_at", sa.DateTime(timezone=True)),
        sa.Column("error", sa.String(2000)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("stopped_at", sa.DateTime(timezone=True)),
        sa.ForeignKeyConstraint(["configuration_id"], ["strategy_configurations.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_paper_sessions_configuration_id", "paper_sessions", ["configuration_id"])
    op.create_index("ix_paper_sessions_status", "paper_sessions", ["status"])
    op.create_table(
        "processed_paper_candles",
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column("strategy", sa.String(32), nullable=False),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["paper_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("session_id", "strategy", "symbol", "interval", "open_time"),
    )


def downgrade() -> None:
    op.drop_table("processed_paper_candles")
    op.drop_index("ix_paper_sessions_status", table_name="paper_sessions")
    op.drop_index("ix_paper_sessions_configuration_id", table_name="paper_sessions")
    op.drop_table("paper_sessions")
