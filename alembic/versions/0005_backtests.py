"""Create immutable backtest run snapshots.

Revision ID: 0005
Revises: 0004
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "backtest_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column("dataset_fingerprints", sa.JSON(), nullable=False),
        sa.Column("result_snapshot", sa.JSON(), nullable=False),
        sa.Column("engine_version", sa.String(length=40), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["job_id"], ["background_jobs.id"], ondelete="SET NULL"
        ),
    )
    op.create_index(
        "ix_backtest_runs_job_id", "backtest_runs", ["job_id"], unique=True
    )
    op.create_index(
        "ix_backtest_runs_fingerprint", "backtest_runs", ["fingerprint"]
    )
    op.create_index(
        "ix_backtest_runs_created_at", "backtest_runs", ["created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_backtest_runs_job_id", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_created_at", table_name="backtest_runs")
    op.drop_index("ix_backtest_runs_fingerprint", table_name="backtest_runs")
    op.drop_table("backtest_runs")
