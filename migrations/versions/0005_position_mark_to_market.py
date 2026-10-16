"""position mark-to-market valuation

Revision ID: 0005
Revises: 0004
Create Date: 2026-10-15 19:20:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0005'
down_revision: str | None = '0004'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # unrealized_pnl becomes nullable: NULL is "not valued", which is
    # semantically different from the 0.0 it used to default to.
    with op.batch_alter_table('positions') as batch_op:
        batch_op.alter_column(
            'unrealized_pnl',
            existing_type=sa.Float(),
            nullable=True,
            server_default=None,
        )
        batch_op.add_column(sa.Column('mark_price', sa.Float(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'valuation_status',
                sa.String(length=16),
                nullable=False,
                server_default='UNKNOWN',
            )
        )
        batch_op.add_column(sa.Column('valuation_reason', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('valuation_as_of', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('positions') as batch_op:
        batch_op.drop_column('valuation_as_of')
        batch_op.drop_column('valuation_reason')
        batch_op.drop_column('valuation_status')
        batch_op.drop_column('mark_price')
        # Back to NOT NULL. Any NULL row is a position that was never valued;
        # 0.0 is the historical default for those, so the downgrade is lossless
        # with respect to the pre-0005 behaviour.
        batch_op.execute(sa.text('UPDATE positions SET unrealized_pnl = 0.0 WHERE unrealized_pnl IS NULL'))
        batch_op.alter_column(
            'unrealized_pnl',
            existing_type=sa.Float(),
            nullable=False,
            server_default='0',
        )
