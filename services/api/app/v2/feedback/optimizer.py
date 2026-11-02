"""
Parameter Optimization & Walk-Forward Learning Engine (PRD Section 9.4).
Simulates parameter sweeps on historical closed trade data, performs walk-forward analysis,
and strictly enforces that LLMs cannot alter production trading parameters autonomously.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.db.models import Trade
from app.v2.db.models import DecisionJournal
from app.v2.ai.schemas import OptimizationResult


class ParameterOptimizer:
    """
    Simulates parameter adjustments on historical trades and performs walk-forward validation.
    """

    DEFAULT_GRID = [
        {"take_profit_pct": 25.0, "trailing_stop_pct": 3.0, "hard_stop_loss_pct": 10.0, "min_entry_score": 70.0},
        {"take_profit_pct": 35.0, "trailing_stop_pct": 5.0, "hard_stop_loss_pct": 12.0, "min_entry_score": 75.0},
        {"take_profit_pct": 50.0, "trailing_stop_pct": 7.0, "hard_stop_loss_pct": 15.0, "min_entry_score": 80.0},
        {"take_profit_pct": 20.0, "trailing_stop_pct": 4.0, "hard_stop_loss_pct": 8.0, "min_entry_score": 65.0},
    ]

    @classmethod
    def run_walk_forward_optimization(
        cls,
        trades: List[Trade],
        parameter_grid: Optional[List[Dict[str, Any]]] = None,
        train_test_split: float = 0.70,
    ) -> OptimizationResult:
        """
        Executes Walk-Forward Optimization across in-sample and out-of-sample data.
        Enforces human approval requirement (Directive & PRD Section 9.4).
        """
        grid = parameter_grid or cls.DEFAULT_GRID
        total_count = len(trades)

        if total_count < 2:
            # Fallback for minimal trade history
            return OptimizationResult(
                strategy_version="2.1-default",
                parameter_set=grid[0],
                in_sample_metrics={"trades": total_count, "winrate_pct": 0.0, "net_pnl": 0.0},
                out_of_sample_metrics={"trades": 0, "winrate_pct": 0.0, "net_pnl": 0.0},
                net_improvement_pct=0.0,
                requires_manual_approval=True,
                approved_by_human=False,
                status="INSUFFICIENT_DATA_FOR_OPTIMIZATION",
            )

        split_idx = max(1, int(total_count * train_test_split))
        in_sample_trades = trades[:split_idx]
        out_of_sample_trades = trades[split_idx:] if split_idx < total_count else in_sample_trades

        # Evaluate grid on In-Sample
        best_params = grid[0]
        best_in_score = -999999.0
        best_in_metrics = {}

        for params in grid:
            sim_metrics = cls._simulate_trade_batch(in_sample_trades, params)
            score = sim_metrics["expectancy"]
            if score > best_in_score:
                best_in_score = score
                best_params = params
                best_in_metrics = sim_metrics

        # Validate on Out-of-Sample (Walk-Forward test)
        out_metrics = cls._simulate_trade_batch(out_of_sample_trades, best_params)

        # Improvement comparison
        baseline_expectancy = best_in_metrics.get("expectancy", 0.0)
        out_expectancy = out_metrics.get("expectancy", 0.0)
        net_improvement = (
            round(((out_expectancy - baseline_expectancy) / abs(baseline_expectancy)) * 100.0, 2)
            if baseline_expectancy != 0.0
            else 0.0
        )

        version_tag = f"2.1-optimized-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"

        return OptimizationResult(
            strategy_version=version_tag,
            parameter_set=best_params,
            in_sample_metrics=best_in_metrics,
            out_of_sample_metrics=out_metrics,
            net_improvement_pct=net_improvement,
            requires_manual_approval=True,  # Mandatory invariant: cannot auto-deploy
            approved_by_human=False,
            status="RECOMMENDED_PENDING_APPROVAL",
        )

    @classmethod
    def _simulate_trade_batch(cls, trade_batch: List[Trade], params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Simulates outcome metrics for a batch of trades under given parameters.
        """
        if not trade_batch:
            return {"trades": 0, "winrate_pct": 0.0, "expectancy": 0.0, "net_pnl": 0.0}

        tp_pct = params.get("take_profit_pct", 30.0)
        sl_pct = params.get("hard_stop_loss_pct", 10.0)

        sim_wins = 0
        sim_losses = 0
        gross_profit = 0.0
        gross_loss = 0.0
        total_pnl = 0.0

        for t in trade_batch:
            raw_pnl = float(t.pnl or 0.0)
            trade_cost = float(t.total or 10.0)

            # Model parameter effects: if trade won, cap at TP or scale by trailing stop
            if raw_pnl > 0:
                scaled_win = min(raw_pnl, trade_cost * (tp_pct / 100.0))
                gross_profit += scaled_win
                total_pnl += scaled_win
                sim_wins += 1
            else:
                capped_loss = max(raw_pnl, -trade_cost * (sl_pct / 100.0))
                gross_loss += abs(capped_loss)
                total_pnl += capped_loss
                sim_losses += 1

        total = len(trade_batch)
        winrate = round((sim_wins / total) * 100.0, 2)
        avg_win = gross_profit / sim_wins if sim_wins > 0 else 0.0
        avg_loss = gross_loss / sim_losses if sim_losses > 0 else 0.0
        expectancy = round(((sim_wins / total) * avg_win) - ((sim_losses / total) * avg_loss), 2)

        return {
            "trades": total,
            "wins": sim_wins,
            "losses": sim_losses,
            "winrate_pct": winrate,
            "expectancy": expectancy,
            "net_pnl": round(total_pnl, 2),
            "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else 999.0,
        }

    @classmethod
    def segment_by_market_regime(cls, db: Session, mode: str = "PAPER") -> Dict[str, Any]:
        """
        Segments closed trade outcomes by market regime: trending, ranging, and choppy.
        Zero synthetic metrics.
        """
        journals = list(
            db.scalars(
                select(DecisionJournal).where(DecisionJournal.mode == mode)
            ).all()
        )

        regimes = {
            "trending": {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "winrate_pct": 0.0},
            "ranging": {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "winrate_pct": 0.0},
            "choppy": {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "winrate_pct": 0.0},
        }

        for j in journals:
            mfe = j.mfe_pct or 0.0
            pnl = j.final_realized_pnl_usd or 0.0

            if mfe >= 30.0:
                bucket = "trending"
            elif mfe >= 10.0:
                bucket = "ranging"
            else:
                bucket = "choppy"

            regimes[bucket]["trades"] += 1
            regimes[bucket]["pnl"] += pnl
            if pnl >= 0:
                regimes[bucket]["wins"] += 1
            else:
                regimes[bucket]["losses"] += 1

        for r_key, data in regimes.items():
            if data["trades"] > 0:
                data["winrate_pct"] = round((data["wins"] / data["trades"]) * 100.0, 1)
                data["pnl"] = round(data["pnl"], 2)

        return regimes
