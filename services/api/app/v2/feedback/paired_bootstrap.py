"""
Advanced Paired Statistical Engine & Sensitivity Analysis (CEO Directive Section 3).
Performs paired bootstrapping, block bootstrapping, distribution moments, and outlier sensitivity
across Strategy A, B, and C.
"""

import math
import random
from typing import List, Dict, Any, Tuple, Optional


class PairedStatisticalEngine:
    """
    Rigorously evaluates statistical significance between strategies using paired observations,
    temporal block bootstrapping, higher distribution moments, and outlier sensitivity.
    """

    @staticmethod
    def compute_distribution_moments(pnls: List[float]) -> Dict[str, Any]:
        """
        Computes the complete distribution profile beyond mean expectancy:
        median, IQR, percentiles (10, 25, 50, 75, 90), skewness, and excess kurtosis.
        """
        n = len(pnls)
        if n == 0:
            return {
                "count": 0, "mean": 0.0, "median": 0.0, "std_dev": 0.0,
                "iqr": 0.0, "p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0,
                "skewness": 0.0, "excess_kurtosis": 0.0
            }

        sorted_pnls = sorted(pnls)
        mean_val = sum(pnls) / n

        def _percentile(data: List[float], p: float) -> float:
            k = (len(data) - 1) * (p / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return data[int(k)]
            d0 = data[int(f)] * (c - k)
            d1 = data[int(c)] * (k - f)
            return d0 + d1

        p10 = round(_percentile(sorted_pnls, 10), 3)
        p25 = round(_percentile(sorted_pnls, 25), 3)
        p50 = round(_percentile(sorted_pnls, 50), 3)  # median
        p75 = round(_percentile(sorted_pnls, 75), 3)
        p90 = round(_percentile(sorted_pnls, 90), 3)
        iqr = round(p75 - p25, 3)

        # Variance and sample standard deviation
        var_val = sum((x - mean_val) ** 2 for x in pnls) / max(1, n - 1) if n > 1 else 0.0
        std_val = math.sqrt(var_val)

        # Skewness and excess kurtosis
        if std_val > 0 and n >= 3:
            m3 = sum((x - mean_val) ** 3 for x in pnls) / n
            m4 = sum((x - mean_val) ** 4 for x in pnls) / n
            skewness = round(m3 / (std_val ** 3), 3)
            excess_kurtosis = round((m4 / (std_val ** 4)) - 3.0, 3)
        else:
            skewness = 0.0
            excess_kurtosis = 0.0

        return {
            "count": n,
            "mean": round(mean_val, 3),
            "median": p50,
            "std_dev": round(std_val, 3),
            "iqr": iqr,
            "p10": p10,
            "p25": p25,
            "p50": p50,
            "p75": p75,
            "p90": p90,
            "skewness": skewness,
            "excess_kurtosis": excess_kurtosis,
        }

    @staticmethod
    def sensitivity_analysis(pnls: List[float]) -> Dict[str, Any]:
        """
        Conducts sensitivity analysis on extreme winners and losers:
        - 1% and 5% Trimmed Means
        - 1% and 5% Winsorized Means
        - Impact of single largest winner (ex-max)
        - Impact of single largest loser (ex-min)
        - Top 3 winners concentration ratio
        """
        n = len(pnls)
        if n == 0:
            return {}

        sorted_pnls = sorted(pnls)
        raw_mean = sum(pnls) / n
        total_pnl = sum(pnls)

        # Trimming
        def _trimmed_mean(data: List[float], pct: float) -> float:
            k = int(len(data) * pct)
            if k == 0 or 2 * k >= len(data):
                return sum(data) / len(data)
            sub = data[k:-k]
            return sum(sub) / len(sub)

        # Winsorizing
        def _winsorized_mean(data: List[float], pct: float) -> float:
            k = int(len(data) * pct)
            if k == 0 or 2 * k >= len(data):
                return sum(data) / len(data)
            low_val = data[k]
            high_val = data[-k - 1]
            mod = [low_val if x < low_val else (high_val if x > high_val else x) for x in data]
            return sum(mod) / len(mod)

        trimmed_1 = round(_trimmed_mean(sorted_pnls, 0.01), 3)
        trimmed_5 = round(_trimmed_mean(sorted_pnls, 0.05), 3)
        winsor_1 = round(_winsorized_mean(sorted_pnls, 0.01), 3)
        winsor_5 = round(_winsorized_mean(sorted_pnls, 0.05), 3)

        # Ex-max and Ex-min
        ex_max_mean = round(sum(sorted_pnls[:-1]) / (n - 1), 3) if n > 1 else raw_mean
        ex_min_mean = round(sum(sorted_pnls[1:]) / (n - 1), 3) if n > 1 else raw_mean

        delta_ex_max = round(raw_mean - ex_max_mean, 3)
        delta_ex_min = round(ex_min_mean - raw_mean, 3)

        # Concentration of top 3 winners
        top3_sum = sum(sorted_pnls[-3:]) if n >= 3 else sum(sorted_pnls)
        top3_share_pct = round((top3_sum / max(total_pnl, 0.01)) * 100.0, 1) if total_pnl > 0 else 0.0

        return {
            "raw_mean_pnl": round(raw_mean, 3),
            "trimmed_mean_1pct": trimmed_1,
            "trimmed_mean_5pct": trimmed_5,
            "winsorized_mean_1pct": winsor_1,
            "winsorized_mean_5pct": winsor_5,
            "ex_max_winner_mean": ex_max_mean,
            "ex_min_loser_mean": ex_min_mean,
            "max_winner_influence": delta_ex_max,
            "max_loser_influence": delta_ex_min,
            "top3_winners_share_pct": top3_share_pct,
            "is_outlier_dominated": top3_share_pct > 60.0,
        }

    @classmethod
    def paired_bootstrap_comparison(
        cls,
        samples_x: List[float],
        samples_y: List[float],
        n_bootstraps: int = 2000,
        alpha: float = 0.05,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Calculates paired difference bootstrap for two synchronized strategies (X vs Y).
        Computes 95% Confidence Interval for (X - Y) and empirical two-sided p-value.
        """
        n = min(len(samples_x), len(samples_y))
        if n == 0:
            return {"mean_difference": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "p_value": 1.0}

        diffs = [samples_x[i] - samples_y[i] for i in range(n)]
        mean_diff = sum(diffs) / n

        rng = random.Random(seed)
        boot_means = []

        for _ in range(n_bootstraps):
            resample = [diffs[rng.randint(0, n - 1)] for _ in range(n)]
            boot_means.append(sum(resample) / n)

        boot_means.sort()
        idx_lower = int(n_bootstraps * (alpha / 2.0))
        idx_upper = int(n_bootstraps * (1.0 - (alpha / 2.0)))

        ci_lower = round(boot_means[idx_lower], 3)
        ci_upper = round(boot_means[idx_upper], 3)

        # Empirical p-value testing H0: mean_diff == 0
        count_le_zero = sum(1 for m in boot_means if m <= 0.0)
        count_ge_zero = sum(1 for m in boot_means if m >= 0.0)
        p_val = round(2.0 * min(count_le_zero / n_bootstraps, count_ge_zero / n_bootstraps), 4)

        # Standard error of difference
        var_diff = sum((d - mean_diff) ** 2 for d in diffs) / (n - 1) if n > 1 else 0.0
        se_diff = math.sqrt(var_diff / n) if n > 0 else 0.0
        t_stat = round(mean_diff / se_diff, 3) if se_diff > 0 else 0.0

        is_statistically_significant = (ci_lower > 0.0 or ci_upper < 0.0) and (p_val < alpha)

        return {
            "n_pairs": n,
            "mean_difference": round(mean_diff, 3),
            "t_statistic": t_stat,
            "p_value": p_val,
            "bootstrap_ci_95": {
                "lower": ci_lower,
                "upper": ci_upper,
            },
            "statistically_significant": is_statistically_significant,
        }

    @classmethod
    def block_bootstrap_comparison(
        cls,
        samples_x: List[float],
        samples_y: List[float],
        block_size: int = 5,
        n_bootstraps: int = 2000,
        alpha: float = 0.05,
        seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Block bootstrap by time/session to preserve temporal autocorrelation and regime clustering.
        """
        n = min(len(samples_x), len(samples_y))
        if n < block_size:
            return cls.paired_bootstrap_comparison(samples_x, samples_y, n_bootstraps, alpha, seed)

        diffs = [samples_x[i] - samples_y[i] for i in range(n)]
        mean_diff = sum(diffs) / n

        # Number of overlapping blocks
        n_blocks = n - block_size + 1
        blocks = [diffs[i:i + block_size] for i in range(n_blocks)]

        rng = random.Random(seed)
        boot_means = []
        num_blocks_needed = math.ceil(n / block_size)

        for _ in range(n_bootstraps):
            resampled_series = []
            for _ in range(num_blocks_needed):
                blk = blocks[rng.randint(0, n_blocks - 1)]
                resampled_series.extend(blk)
            resampled_series = resampled_series[:n]
            boot_means.append(sum(resampled_series) / n)

        boot_means.sort()
        idx_lower = int(n_bootstraps * (alpha / 2.0))
        idx_upper = int(n_bootstraps * (1.0 - (alpha / 2.0)))

        ci_lower = round(boot_means[idx_lower], 3)
        ci_upper = round(boot_means[idx_upper], 3)

        count_le_zero = sum(1 for m in boot_means if m <= 0.0)
        count_ge_zero = sum(1 for m in boot_means if m >= 0.0)
        p_val = round(2.0 * min(count_le_zero / n_bootstraps, count_ge_zero / n_bootstraps), 4)

        return {
            "block_size": block_size,
            "mean_difference": round(mean_diff, 3),
            "block_bootstrap_ci_95": {
                "lower": ci_lower,
                "upper": ci_upper,
            },
            "block_p_value": p_val,
            "statistically_significant": (ci_lower > 0.0 or ci_upper < 0.0) and (p_val < alpha),
        }
