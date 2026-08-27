"""Create immutable candle datasets and validation issues.

Revision ID: 0002
Revises: 0001
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "candle_datasets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("interval", sa.String(length=8), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("candle_count", sa.Integer(), nullable=False),
        sa.Column("is_valid", sa.Boolean(), nullable=False),
        sa.Column("reference_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("fingerprint", name="uq_candle_datasets_fingerprint"),
    )
    op.create_index("ix_candle_datasets_symbol", "candle_datasets", ["symbol"])
    op.create_index("ix_candle_datasets_interval", "candle_datasets", ["interval"])
    op.create_table(
        "candles",
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("open_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open", sa.Numeric(38, 18), nullable=False),
        sa.Column("high", sa.Numeric(38, 18), nullable=False),
        sa.Column("low", sa.Numeric(38, 18), nullable=False),
        sa.Column("close", sa.Numeric(38, 18), nullable=False),
        sa.Column("volume", sa.Numeric(38, 18), nullable=False),
        sa.Column("close_time", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["candle_datasets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("dataset_id", "open_time"),
    )
    op.create_table(
        "dataset_validation_issues",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("dataset_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("message", sa.String(length=255), nullable=False),
        sa.Column("open_time", sa.String(length=40), nullable=True),
        sa.ForeignKeyConstraint(
            ["dataset_id"], ["candle_datasets.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("dataset_validation_issues")
    op.drop_table("candles")
    op.drop_index("ix_candle_datasets_interval", table_name="candle_datasets")
    op.drop_index("ix_candle_datasets_symbol", table_name="candle_datasets")
    op.drop_table("candle_datasets")
