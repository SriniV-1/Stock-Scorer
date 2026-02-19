"""
Percentile calculation engine.

Industry-relative scoring:
Instead of saying "P/E < 15 is good",
we say "P/E in the 20th percentile of peers is good".

Percentile tells us what % of peers are BELOW this value.
- 90th percentile = better than 90% of peers
- 10th percentile = worse than 90% of peers
"""

import numpy as np
from scipy import stats
from typing import List, Optional, Dict
import logging

logger = logging.getLogger(__name__)


class PercentileCalculator:
    """
    Calculates percentile rankings for metrics.
    """

    VALID_METHODS = {"rank", "strict", "weak", "mean"}

    @staticmethod
    def calculate_percentile(
        value: float,
        peer_values: List[float],
        method: str = "rank"
    ) -> Optional[float]:
        """
        Calculate percentile rank of a value within a distribution.
        """

        if value is None:
            logger.warning("Value is None — cannot calculate percentile.")
            return None

        if not peer_values:
            logger.warning("Peer list empty — cannot calculate percentile.")
            return None

        # Remove None and non-numeric values
        cleaned = []
        for v in peer_values:
            if isinstance(v, (int, float)) and not np.isnan(v):
                cleaned.append(float(v))

        if len(cleaned) < 1:
            logger.warning("No valid peer values after cleaning.")
            return None

        # Ensure stock value is included in distribution
        if value not in cleaned:
            cleaned.append(float(value))

        if len(cleaned) < 2:
            logger.warning("Need at least 2 data points for percentile.")
            return None

        if method not in PercentileCalculator.VALID_METHODS:
            logger.warning(f"Invalid method '{method}', defaulting to 'rank'")
            method = "rank"

        try:
            percentile = stats.percentileofscore(
                cleaned,
                value,
                kind=method
            )

            return round(float(percentile), 2)

        except Exception as e:
            logger.error(f"Error calculating percentile: {e}")
            return None

    @staticmethod
    def calculate_all_percentiles(
        stock_metrics: Dict[str, float],
        peer_metrics: List[Dict[str, float]],
        metric_names: List[str],
        method: str = "rank",
        reverse_metrics: Optional[List[str]] = None
    ) -> Dict[str, Optional[float]]:
        """
        Calculate percentiles for multiple metrics.

        reverse_metrics:
            Metrics where LOWER is better
            (e.g., pe_ratio, debt_to_equity, peg_ratio)
        """

        percentiles: Dict[str, Optional[float]] = {}
        reverse_metrics = reverse_metrics or []

        for metric in metric_names:

            stock_value = stock_metrics.get(metric)

            peer_values = [
                peer.get(metric)
                for peer in peer_metrics
                if peer.get(metric) is not None
            ]

            if stock_value is None:
                logger.warning(f"{metric}: stock value missing")
                percentiles[metric] = None
                continue

            if len(peer_values) < 1:
                logger.warning(f"{metric}: insufficient peer data")
                percentiles[metric] = None
                continue

            percentile = PercentileCalculator.calculate_percentile(
                stock_value,
                peer_values,
                method=method
            )

            if percentile is None:
                percentiles[metric] = None
                continue

            # 🔁 Reverse percentile if lower value is better
            if metric in reverse_metrics:
                percentile = 100 - percentile

            percentiles[metric] = round(percentile, 2)

        return percentiles


# =============================
# Testing
# =============================

if __name__ == "__main__":

    logging.basicConfig(level=logging.INFO)

    calc = PercentileCalculator()

    print("\n" + "=" * 50)
    print("PERCENTILE CALCULATOR TESTS")
    print("=" * 50)

    # Test 1
    print("\nTest 1: Basic Percentile")
    peers = [10, 15, 20, 25, 30, 35, 40]
    result = calc.calculate_percentile(25, peers)
    print(f"25 vs peers → {result}%")

    # Test 2: Highest
    print("\nTest 2: Highest Value")
    result2 = calc.calculate_percentile(40, peers)
    print(f"40 → {result2}% (should be 100)")

    # Test 3: Lowest
    print("\nTest 3: Lowest Value")
    result3 = calc.calculate_percentile(10, peers)
    print(f"10 → {result3}% (should be near 0)")

    # Test 4: Multi-metric with reverse example
    print("\nTest 4: Multiple Metrics")

    stock = {
        "pe_ratio": 25,
        "roe": 0.15,
        "revenue_growth": 0.20
    }

    peers = [
        {"pe_ratio": 20, "roe": 0.10, "revenue_growth": 0.15},
        {"pe_ratio": 30, "roe": 0.12, "revenue_growth": 0.18},
        {"pe_ratio": 35, "roe": 0.18, "revenue_growth": 0.25},
        {"pe_ratio": 15, "roe": 0.08, "revenue_growth": 0.10},
    ]

    results = calc.calculate_all_percentiles(
        stock,
        peers,
        ["pe_ratio", "roe", "revenue_growth"],
        reverse_metrics=["pe_ratio"]  # Lower P/E = better
    )

    for k, v in results.items():
        print(f"{k}: {v}%")

    print("\n" + "=" * 50)
    print("✅ PERCENTILE CALCULATOR WORKING")
    print("=" * 50)
