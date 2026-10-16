"""trace exit fills to real order intents

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-13
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # A close used to write `bot_run_id` into `fills.order_id`, which points at
    # `order_intents.id`. Every exit fill was therefore an unresolvable
    # reference. Positions now carry the opening signal and the exit order so
    # both sides of a trade stay traceable (FR-TB-008).
    with op.batch_alter_table("fills") as batch_op:
        batch_op.add_column(
            sa.Column("side", sa.String(length=4), nullable=False, server_default="BUY")
        )

    with op.batch_alter_table("positions") as batch_op:
        batch_op.add_column(sa.Column("open_order_intent_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("open_signal_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("exit_order_intent_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_positions_open_order_intent_id", "order_intents", ["open_order_intent_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_positions_open_signal_id", "signals", ["open_signal_id"], ["id"]
        )
        batch_op.create_foreign_key(
            "fk_positions_exit_order_intent_id", "order_intents", ["exit_order_intent_id"], ["id"]
        )


def downgrade() -> None:
    with op.batch_alter_table("positions") as batch_op:
        batch_op.drop_constraint("fk_positions_exit_order_intent_id", type_="foreignkey")
        batch_op.drop_constraint("fk_positions_open_signal_id", type_="foreignkey")
        batch_op.drop_constraint("fk_positions_open_order_intent_id", type_="foreignkey")
        batch_op.drop_column("exit_order_intent_id")
        batch_op.drop_column("open_signal_id")
        batch_op.drop_column("open_order_intent_id")

    with op.batch_alter_table("fills") as batch_op:
        batch_op.drop_column("side")