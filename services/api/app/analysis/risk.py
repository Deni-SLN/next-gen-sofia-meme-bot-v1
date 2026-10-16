"""Deterministic risk assessment with hard-reject rules (FR-AE-005).

UNKNOWN != PASS. Mandatory safety checks that cannot be verified fail closed.
"""

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime

DEFAULT_RULES: dict = {
    "rule_version": "risk-v1",
    "min_liquidity_usd": 5000.0,
    "min_pool_age_minutes": 30.0,
    "min_buys_1h": 10,
    "reject_if_mint_authority": True,
    "reject_if_freeze_authority": True,
    "max_top10_holder_pct": 0.50,
    # Checks that MUST be verifiable. A mandatory check that cannot be
    # confirmed is a hard reject, never a pass and never a soft warning.
    "mandatory_checks": [
        "price_valid",
        "liquidity_valid",
        "pool_age_known",
        "mint_authority",
        "freeze_authority",
    ],
}

# Which flag marks a mandatory check as unverified. Data-driven so the rule set
# and the flags cannot drift apart.
MANDATORY_UNKNOWN_FLAGS: dict[str, str] = {
    "price_valid": "INVALID_PRICE",
    "liquidity_valid": "INVALID_LIQUIDITY",
    "pool_age_known": "POOL_AGE_UNKNOWN",
    "mint_authority": "MINT_AUTHORITY_UNKNOWN",
    "freeze_authority": "FREEZE_AUTHORITY_UNKNOWN",
    "holder_concentration": "HOLDER_CONCENTRATION_UNKNOWN",
}


@dataclass
class RiskInput:
    price_usd: float | None
    liquidity_usd: float | None
    pool_age_minutes: float | None
    buys_1h: int | None
    sells_1h: int | None
    mint_authority_revoked: bool | None
    freeze_authority_revoked: bool | None
    top10_holder_pct: float | None
    allocation_usd: float | None = None


@dataclass
class RiskResult:
    status: str  # PASS | WARN | REJECT | UNKNOWN
    hard_reject: bool
    risk_flags: list[str] = field(default_factory=list)
    coverage: float = 0.0
    rule_version: str = "risk-v1"
    evidence_refs: list[dict] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    assessed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


def _finite(x) -> bool:
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def assess_risk(data: RiskInput, rules: dict | None = None) -> RiskResult:
    r = {**DEFAULT_RULES, **(rules or {})}
    flags: list[str] = []
    reasons: list[str] = []
    evidence: list[dict] = []
    hard = False

    price_ok = _finite(data.price_usd) and data.price_usd > 0
    if not price_ok:
        hard = True
        flags.append("INVALID_PRICE")
        reasons.append("price missing or non-positive")
    evidence.append({"check": "price_valid", "result": price_ok, "value": data.price_usd})

    liq_ok = _finite(data.liquidity_usd) and data.liquidity_usd > 0
    if not liq_ok:
        hard = True
        flags.append("INVALID_LIQUIDITY")
        reasons.append("liquidity missing or non-positive")
    elif data.liquidity_usd < r["min_liquidity_usd"]:
        hard = True
        flags.append("LOW_LIQUIDITY")
        reasons.append(f"liquidity {data.liquidity_usd:.0f} < min {r['min_liquidity_usd']:.0f}")
    evidence.append({"check": "liquidity_valid", "result": liq_ok, "value": data.liquidity_usd})

    age_known = _finite(data.pool_age_minutes)
    if not age_known:
        flags.append("POOL_AGE_UNKNOWN")
        reasons.append("pool age could not be verified")
    elif data.pool_age_minutes < r["min_pool_age_minutes"]:
        hard = True
        flags.append("POOL_TOO_YOUNG")
        reasons.append(f"pool age {data.pool_age_minutes:.0f}m < min {r['min_pool_age_minutes']:.0f}m")
    evidence.append({"check": "pool_age_known", "result": age_known, "value": data.pool_age_minutes})

    if data.mint_authority_revoked is None:
        flags.append("MINT_AUTHORITY_UNKNOWN")
        reasons.append("mint authority status unknown")
    elif not data.mint_authority_revoked:
        flags.append("MINT_AUTHORITY_ENABLED")
        if r["reject_if_mint_authority"]:
            hard = True
            reasons.append("mint authority still enabled")
        else:
            reasons.append("mint authority still enabled (warn policy)")
    evidence.append({"check": "mint_authority", "revoked": data.mint_authority_revoked})

    if data.freeze_authority_revoked is None:
        flags.append("FREEZE_AUTHORITY_UNKNOWN")
        reasons.append("freeze authority status unknown")
    elif not data.freeze_authority_revoked:
        flags.append("FREEZE_AUTHORITY_ENABLED")
        if r["reject_if_freeze_authority"]:
            hard = True
            reasons.append("freeze authority still enabled")
        else:
            reasons.append("freeze authority still enabled (warn policy)")
    evidence.append({"check": "freeze_authority", "revoked": data.freeze_authority_revoked})

    holder_known = _finite(data.top10_holder_pct)
    if not holder_known:
        flags.append("HOLDER_CONCENTRATION_UNKNOWN")
        reasons.append("holder concentration unknown")
    elif data.top10_holder_pct > r["max_top10_holder_pct"]:
        flags.append("HOLDER_CONCENTRATION")
        reasons.append(f"top10 holders {data.top10_holder_pct:.0%} > limit")
        if data.top10_holder_pct > 0.80:
            hard = True
    evidence.append({"check": "holder_concentration", "result": holder_known, "value": data.top10_holder_pct})

    if _finite(data.buys_1h) and data.buys_1h < r["min_buys_1h"]:
        flags.append("LOW_ACTIVITY")
        reasons.append(f"buys_1h {data.buys_1h} < {r['min_buys_1h']}")
    evidence.append({"check": "activity", "buys_1h": data.buys_1h, "sells_1h": data.sells_1h})

    coverage = sum(
        1 for c in (
            price_ok,
            liq_ok,
            age_known,
            data.mint_authority_revoked is not None,
            data.freeze_authority_revoked is not None,
            holder_known,
        )
        if c
    ) / 6.0

    # Mandatory checks that cannot be verified: fail closed.
    unknown_mandatory: list[str] = []
    mandatory = r.get("mandatory_checks") or []
    for check_name in mandatory:
        flag = MANDATORY_UNKNOWN_FLAGS.get(check_name)
        if flag is None:
            raise ValueError(f"unknown mandatory check: {check_name!r}")
        if flag in flags:
            unknown_mandatory.append(flag)
    if unknown_mandatory:
        hard = True
        reasons.append(
            "mandatory safety checks unknown -> fail-closed hard reject: "
            + ", ".join(unknown_mandatory)
        )

    # Status is derived last so it can never contradict hard_reject.
    if hard:
        status = "REJECT"
    elif flags:
        status = "WARN"
    else:
        status = "PASS"

    return RiskResult(
        status=status,
        hard_reject=hard,
        risk_flags=flags,
        coverage=coverage,
        rule_version=r["rule_version"],
        evidence_refs=evidence,
        reasons=reasons,
    )

