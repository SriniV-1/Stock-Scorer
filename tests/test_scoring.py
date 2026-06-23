"""
Unit tests for the scoring pipeline.

These cover the pure-math core (percentiles, metric scoring, category
aggregation, final weighting, interpretation) with no network access, so they
run fast and deterministically in CI.
"""

import math

import pytest

from src.scoring.percentile import PercentileCalculator
from src.scoring.metric_scorer import MetricScorer
from src.scoring.category_aggregator import CategoryAggregator
from src.scoring.final_scorer import FinalScorer
from src.utils.config import CATEGORY_WEIGHTS


# --------------------------------------------------------------------------- #
# Percentiles
# --------------------------------------------------------------------------- #
class TestPercentile:
    def test_highest_value_scores_near_top(self):
        p = PercentileCalculator.calculate_percentile(100, [10, 20, 30, 40])
        assert p is not None and p >= 80

    def test_lowest_value_scores_near_bottom(self):
        p = PercentileCalculator.calculate_percentile(1, [10, 20, 30, 40])
        assert p is not None and p <= 30

    def test_median_value_is_mid_range(self):
        p = PercentileCalculator.calculate_percentile(25, [10, 20, 30, 40])
        assert 30 <= p <= 70

    def test_none_value_returns_none(self):
        assert PercentileCalculator.calculate_percentile(None, [1, 2, 3]) is None

    def test_empty_peers_returns_none(self):
        assert PercentileCalculator.calculate_percentile(5, []) is None

    def test_nan_peers_are_filtered(self):
        p = PercentileCalculator.calculate_percentile(50, [10, float("nan"), 90])
        assert p is not None and not math.isnan(p)


# --------------------------------------------------------------------------- #
# Metric scoring (direction handling)
# --------------------------------------------------------------------------- #
class TestMetricScorer:
    def setup_method(self):
        self.scorer = MetricScorer()

    def test_higher_is_better_passthrough(self):
        # ROE: higher percentile => higher score
        assert self.scorer.score_from_percentile(80, "roe", "profitability") == 80

    def test_lower_is_better_inverts(self):
        # A high P/E percentile means EXPENSIVE => low score
        assert self.scorer.score_from_percentile(80, "pe_ratio", "valuation") == 20

    def test_lower_is_better_inversion_symmetry(self):
        s = self.scorer.score_from_percentile(30, "debt_to_equity", "risk")
        assert s == 70

    def test_none_percentile_returns_none(self):
        assert self.scorer.score_from_percentile(None, "roe", "profitability") is None

    def test_scores_bounded_0_100(self):
        for pct in (0, 25, 50, 75, 100):
            s = self.scorer.score_from_percentile(pct, "roe", "profitability")
            assert 0 <= s <= 100


# --------------------------------------------------------------------------- #
# Final weighting + interpretation
# --------------------------------------------------------------------------- #
class TestFinalScorer:
    def setup_method(self):
        self.scorer = FinalScorer()

    def test_weights_match_config(self):
        assert self.scorer.category_weights == CATEGORY_WEIGHTS

    def test_all_max_scores_is_100(self):
        scores = {c: 100 for c in CATEGORY_WEIGHTS}
        result = self.scorer.calculate_final_score(scores)
        assert result["final_score"] == pytest.approx(100, abs=0.5)

    def test_all_min_scores_is_0(self):
        scores = {c: 0 for c in CATEGORY_WEIGHTS}
        result = self.scorer.calculate_final_score(scores)
        assert result["final_score"] == pytest.approx(0, abs=0.5)

    def test_weighted_average_is_correct(self):
        # valuation .30, growth .25, profitability .25, risk .20
        scores = {"valuation": 60, "growth": 80, "profitability": 70, "risk": 50}
        expected = 60 * 0.30 + 80 * 0.25 + 70 * 0.25 + 50 * 0.20  # = 65.5
        result = self.scorer.calculate_final_score(scores)
        assert result["final_score"] == pytest.approx(expected, abs=0.5)

    def test_custom_weights_normalized(self):
        # Weights that don't sum to 1.0 should be normalized, not rejected.
        scorer = FinalScorer({"valuation": 2, "growth": 2, "profitability": 2, "risk": 2})
        assert sum(scorer.category_weights.values()) == pytest.approx(1.0, abs=1e-6)

    @pytest.mark.parametrize(
        "score,expected_rating",
        [(95, "Excellent"), (70, "Good"), (55, "Average"),
         (40, "Below Average"), (10, "Poor")],
    )
    def test_interpretation_thresholds(self, score, expected_rating):
        assert self.scorer.interpret_score(score)["rating"] == expected_rating


# --------------------------------------------------------------------------- #
# Category aggregation
# --------------------------------------------------------------------------- #
class TestCategoryAggregator:
    def setup_method(self):
        self.agg = CategoryAggregator()

    def test_aggregate_all_returns_each_category(self):
        # Feed real percentiles through the scorer so the aggregator receives
        # the {metric: {score, ...}} shape it expects from score_all_metrics().
        percentiles = {
            "pe_ratio": 70, "peg_ratio": 60, "price_to_fcf": 50,
            "revenue_growth": 80, "eps_growth": 90,
            "roe": 75, "operating_margin": 65, "net_margin": 70,
            "debt_to_equity": 40, "current_ratio": 55, "beta": 60,
        }
        metric_scores = MetricScorer().score_all_metrics(percentiles)
        result = self.agg.aggregate_all_categories(metric_scores)
        for category in CATEGORY_WEIGHTS:
            assert category in result
            assert result[category]["score"] is not None
