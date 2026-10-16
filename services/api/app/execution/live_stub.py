"""Live execution adapter — DISABLED INTERFACE (FR-TB-006).

This adapter is a stub interface only. It must remain disabled until the
readiness criteria in FR-TB-006 are met and the operator gives explicit
approval. Starting LIVE in V1 is always rejected by the bot service.
"""

from app.core.config import settings
from app.core.errors import ForbiddenError


class LiveExecutionDisabledError(ForbiddenError):
    def __init__(self) -> None:
        super().__init__(
            "Live trading is disabled for this release. "
            "Activation requires explicit operator approval and readiness criteria (FR-TB-006).",
            details={"feature": "live_execution", "enabled": False},
        )


class LiveExecutionAdapter:
    """Interface placeholder. Every mutating method raises."""

    name = "live"

    @property
    def enabled(self) -> bool:
        # Even if the env flag were flipped, V1 ships without an implementation.
        return False

    async def submit_order(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise LiveExecutionDisabledError()

    async def cancel_order(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise LiveExecutionDisabledError()

    async def get_balances(self, *args, **kwargs):  # noqa: ANN002, ANN003
        raise LiveExecutionDisabledError()


def assert_live_allowed() -> None:
    """Server-side gate: V1 always rejects live start regardless of request."""
    if not settings.live_trading_enabled:
        raise LiveExecutionDisabledError()
    raise LiveExecutionDisabledError()  # no live implementation ships in V1
