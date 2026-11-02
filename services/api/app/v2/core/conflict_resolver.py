"""
Conflict Resolver for SOFIA MEME BOT V2.
Enforces multi-agent decision authority and conflict resolution invariants.
Strictly adheres to:
- PRD Section 8.1 (Decision Authority)
- PRD Section 8.2 (Conflict Resolution Scenarios A, B, C, D, E)
"""

import logging
from typing import Optional
from app.v2.ai.schemas import ConflictResolutionOutput

logger = logging.getLogger("sofia.v2.conflict_resolver")


class ConflictResolver:
    """
    Arbitrates conflicts between Entry Agent, Exit Agent, Risk Engine,
    and Deterministic Safety Policies.
    Rule: Deterministic Risk holds absolute veto authority over AI opinions.
    """

    @classmethod
    def resolve_entry_conflict(
        cls,
        entry_decision: str,
        risk_veto: bool = False,
        veto_reason: Optional[str] = None,
        is_stale_data: bool = False,
        ai_provider_available: bool = True,
        current_open_positions: int = 0,
        max_open_positions: int = 5,
        daily_drawdown_limit_hit: bool = False,
    ) -> ConflictResolutionOutput:
        """
        Arbitrates entry decisions according to PRD Section 8.2.
        """
        # Scenario G: Daily Drawdown Circuit Breaker
        if daily_drawdown_limit_hit:
            return ConflictResolutionOutput(
                scenario="DAILY_DRAWDOWN_LIMIT",
                entry_recommendation=entry_decision,
                risk_veto_active=True,
                resolution="HALT_DAILY_DRAWDOWN",
                action="REJECT",
                reasoning="Sistem menghentikan entri baru: Batas akumulasi kerugian harian (Daily Drawdown) tercapai.",
                priority_component="Risk Engine (Circuit Breaker)",
                is_blocked=True,
            )

        # Scenario D: Stale Market Data
        if is_stale_data:
            return ConflictResolutionOutput(
                scenario="SCENARIO_D_STALE_DATA",
                entry_recommendation=entry_decision,
                risk_veto_active=True,
                resolution="HOLD_NO_BUY",
                action="SKIP",
                reasoning="Data pasar kadaluarsa (>180 detik). Dilarang membuka posisi baru saat feed data tidak segar.",
                priority_component="Data Quality Gate",
                is_blocked=True,
            )

        # Scenario E: AI Provider Outage
        if not ai_provider_available:
            return ConflictResolutionOutput(
                scenario="SCENARIO_E_AI_PROVIDER_UNAVAILABLE",
                entry_recommendation=entry_decision,
                risk_veto_active=True,
                resolution="DETERMINISTIC_FALLBACK",
                action="WAIT",
                reasoning="Penyedia model AI sedang tidak merespon / offline. Entri baru dibekukan demi keamanan modal.",
                priority_component="System Orchestrator",
                is_blocked=True,
            )

        # Scenario F: Capacity Limit
        if current_open_positions >= max_open_positions and entry_decision == "BUY":
            return ConflictResolutionOutput(
                scenario="MAX_CAPACITY_REACHED",
                entry_recommendation=entry_decision,
                risk_veto_active=True,
                resolution="REJECT",
                action="SKIP",
                reasoning=f"Kapasitas posisi penuh ({current_open_positions}/{max_open_positions}). Dilarang membuka trade baru.",
                priority_component="Position Manager",
                is_blocked=True,
            )

        # Scenario A: Entry Agent recommends BUY, Risk Engine rejects
        if entry_decision == "BUY" and risk_veto:
            return ConflictResolutionOutput(
                scenario="SCENARIO_A_ENTRY_VS_RISK",
                entry_recommendation="BUY",
                risk_veto_active=True,
                resolution="REJECT",
                action="REJECT",
                reasoning=f"Entry Agent merekomendasikan BUY, tetapi Risk Engine menolak (VETO): {veto_reason or 'Risk violation'}.",
                priority_component="Risk Engine (Veto Authority)",
                is_blocked=True,
            )

        # Non-conflict standard entry
        if entry_decision == "BUY" and not risk_veto:
            return ConflictResolutionOutput(
                scenario="CONSENSUS_BUY_APPROVED",
                entry_recommendation="BUY",
                risk_veto_active=False,
                resolution="PROCEED",
                action="BUY",
                reasoning="Entry Agent menyetujui dan Risk Engine mengonfirmasi parameter aman.",
                priority_component="Trade Supervisor",
                is_blocked=False,
            )

        return ConflictResolutionOutput(
            scenario="STANDARD_ENTRY_EVALUATION",
            entry_recommendation=entry_decision,
            risk_veto_active=False,
            resolution="PROCEED",
            action=entry_decision,
            reasoning=f"Keputusan entri konsensual: {entry_decision}.",
            priority_component="Entry Agent",
            is_blocked=entry_decision in ("SKIP", "WAIT"),
        )

    @classmethod
    def resolve_exit_conflict(
        cls,
        exit_decision: str,
        policy_action: str,
        policy_override: bool = False,
        policy_reason: Optional[str] = None,
        is_stale_data: bool = False,
        ai_provider_available: bool = True,
    ) -> ConflictResolutionOutput:
        """
        Arbitrates exit decisions according to PRD Section 8.2.
        """
        # Scenario B: Exit Agent recommends HOLD, deterministic stop-loss triggers
        if policy_override and policy_action in ("FULL_EXIT", "EMERGENCY_EXIT"):
            return ConflictResolutionOutput(
                scenario="SCENARIO_B_HOLD_VS_HARD_STOP",
                exit_recommendation=exit_decision,
                risk_veto_active=True,
                resolution="SELL",
                action=policy_action,
                reasoning=f"Kebijakan proteksi deterministik memveto rekomendasi AI '{exit_decision}': {policy_reason}.",
                priority_component="Deterministic Exit Policy (VETO AUTHORITY)",
                is_blocked=False,
            )

        # Scenario C: Exit Agent recommends REDUCE, Risk Engine confirms execution is safe
        if exit_decision in ("REDUCE", "TAKE_PROFIT") or policy_action.startswith("REDUCE_"):
            return ConflictResolutionOutput(
                scenario="SCENARIO_C_PARTIAL_EXIT",
                exit_recommendation=exit_decision,
                risk_veto_active=False,
                resolution="PARTIAL_SELL",
                action=policy_action if policy_action.startswith("REDUCE_") else "REDUCE",
                reasoning="Exit Agent & Profit Policy menyetujui likuidasi parsial untuk mengamankan profit.",
                priority_component="Partial Exit Manager",
                is_blocked=False,
            )

        # Scenario E: AI Provider offline during exit
        if not ai_provider_available:
            return ConflictResolutionOutput(
                scenario="SCENARIO_E_EXIT_AI_OFFLINE",
                exit_recommendation=exit_decision,
                risk_veto_active=False,
                resolution="DETERMINISTIC_FALLBACK",
                action=policy_action,
                reasoning="AI Provider offline. Evaluasi exit beralih penuh ke aturan deterministik trailing stop & hard stop.",
                priority_component="Deterministic Fallback Core",
                is_blocked=False,
            )

        # Default consensus
        return ConflictResolutionOutput(
            scenario="CONSENSUS_EXIT_EVALUATION",
            exit_recommendation=exit_decision,
            risk_veto_active=False,
            resolution="PROCEED",
            action=exit_decision,
            reasoning=f"Keputusan exit konsensual: {exit_decision}.",
            priority_component="Exit Intelligence",
            is_blocked=False,
        )


# Singleton
conflict_resolver = ConflictResolver()
