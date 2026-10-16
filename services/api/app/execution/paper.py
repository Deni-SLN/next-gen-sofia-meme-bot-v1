"""Paper execution adapter (FR-TB-005).

Uses real market prices but virtual cash. Simulates fee, slippage, and
rejection. Never signs or sends blockchain transactions. All fills are
clearly marked SIMULATED.
"""

from dataclasses import dataclass


@dataclass
class PaperFill:
    quantity: float
    price: float
    fee_amount: float
    slippage: float
    fill_type: str = "SIMULATED"
    rejected: bool = False
    reject_reason: str | None = None


def simulate_buy(
    allocation_usd: float,
    reference_price: float,
    slippage_pct: float,
    fee_pct: float,
) -> PaperFill:
    """Simulate a market buy. Slippage worsens entry price; fee charged on notional."""
    if allocation_usd <= 0 or reference_price <= 0:
        return PaperFill(
            quantity=0.0,
            price=0.0,
            fee_amount=0.0,
            slippage=0.0,
            rejected=True,
            reject_reason="invalid allocation or price",
        )
    slip = max(0.0, slippage_pct) / 100.0
    fee = max(0.0, fee_pct) / 100.0
    fill_price = reference_price * (1.0 + slip)
    # fee taken from notional
    spend_after_fee = allocation_usd * (1.0 - fee)
    quantity = spend_after_fee / fill_price if fill_price > 0 else 0.0
    fee_amount = allocation_usd * fee
    return PaperFill(
        quantity=quantity,
        price=fill_price,
        fee_amount=fee_amount,
        slippage=slip,
        fill_type="SIMULATED",
    )


def simulate_sell(
    quantity: float,
    reference_price: float,
    slippage_pct: float,
    fee_pct: float,
) -> PaperFill:
    if quantity <= 0 or reference_price <= 0:
        return PaperFill(
            quantity=0.0,
            price=0.0,
            fee_amount=0.0,
            slippage=0.0,
            rejected=True,
            reject_reason="invalid quantity or price",
        )
    slip = max(0.0, slippage_pct) / 100.0
    fee = max(0.0, fee_pct) / 100.0
    fill_price = reference_price * (1.0 - slip)
    notional = quantity * fill_price
    fee_amount = notional * fee
    return PaperFill(
        quantity=quantity,
        price=fill_price,
        fee_amount=fee_amount,
        slippage=slip,
        fill_type="SIMULATED",
    )
