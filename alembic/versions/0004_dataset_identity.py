"""Scope candle dataset identity to its metadata.

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    constraint = next(
        item
        for item in sa.inspect(bind).get_unique_constraints("candle_datasets")
        if item["column_names"] == ["fingerprint"]
    )
    constraint_name = constraint["name"] or "uq_candle_datasets_fingerprint"
    with op.batch_alter_table(
        "candle_datasets",
        naming_convention={"uq": "uq_%(table_name)s_%(column_0_name)s"},
    ) as batch_op:
        batch_op.drop_constraint(constraint_name, type_="unique")
        batch_op.create_unique_constraint(
            "uq_candle_dataset_identity",
            ["symbol", "interval", "start_time", "end_time", "fingerprint"],
        )


def downgrade() -> None:
    with op.batch_alter_table("candle_datasets") as batch_op:
        batch_op.drop_constraint("uq_candle_dataset_identity", type_="unique")
        batch_op.create_unique_constraint(
            "uq_candle_datasets_fingerprint", ["fingerprint"]
        )
