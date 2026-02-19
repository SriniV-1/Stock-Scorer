"""
Main scoring engine - orchestrates the entire pipeline.
"""

import logging
from typing import Dict, Optional
from datetime import datetime

from src.data.peer_manager import PeerDataManager
from src.scoring.percentile import PercentileCalculator
from src.scoring.metric_scorer import MetricScorer
from src.scoring.category_aggregator import CategoryAggregator
from src.scoring.adjustments import ContextualAdjuster
from src.scoring.final_scorer import FinalScorer
from src.utils.config import METRICS
from src.utils.models import ScoringResult, CategoryScore, MetricScore

logger = logging.getLogger(__name__)


class StockScoringEngine:

    def __init__(self, db_path: str = "data/peers.db"):
        self.peer_manager = PeerDataManager(db_path)
        self.percentile_calc = PercentileCalculator()
        self.metric_scorer = MetricScorer()
        self.category_aggregator = CategoryAggregator()
        self.adjuster = ContextualAdjuster()
        self.final_scorer = FinalScorer()

        logger.info("StockScoringEngine initialized")

    def score_stock(
        self,
        ticker: str,
        force_refresh: bool = False,
        custom_weights: Optional[Dict] = None
    ) -> Optional[ScoringResult]:

        ticker = ticker.upper()
        logger.info(f"Starting scoring pipeline for {ticker}")

        try:
            # Step 1: Fetch peer data
            logger.info("Step 1: Fetching peer data...")
            peer_data = self.peer_manager.get_peer_metrics(
                ticker,
                force_refresh=force_refresh
            )

            if ticker not in peer_data:
                logger.error(f"Failed to fetch data for {ticker}")
                return None

            stock_metrics = peer_data[ticker]
            peer_count = len(peer_data)

            logger.info(f"Fetched data for {ticker} + {peer_count-1} peers")

            # Step 2: Convert to dict format
            stock_dict = self._metrics_to_dict(stock_metrics)
            peer_dicts = [
                self._metrics_to_dict(m)
                for m in peer_data.values()
            ]

            # Step 3: Calculate percentiles
            logger.info("Step 2: Calculating percentiles...")
            metric_names = self._get_all_metric_names()

            reverse_metrics = [
                "pe_ratio",
                "peg_ratio",
                "price_to_fcf",
                "debt_to_equity",
                "beta"
            ]

            percentiles = self.percentile_calc.calculate_all_percentiles(
                stock_dict,
                peer_dicts,
                metric_names,
                reverse_metrics=reverse_metrics
            )

            logger.info(f"Calculated percentiles for {len(percentiles)} metrics")

            # Step 4: Score metrics
            logger.info("Step 3: Scoring metrics...")
            metric_scores = self.metric_scorer.score_all_metrics(percentiles)

            # Step 5: Aggregate categories
            logger.info("Step 4: Aggregating categories...")
            category_results = self.category_aggregator.aggregate_all_categories(
                metric_scores
            )

            # Step 6: Apply contextual adjustments
            logger.info("Step 5: Applying contextual adjustments...")
            adjustment_result = self.adjuster.apply_all_adjustments(
                category_results,
                stock_dict
            )

            adjusted_scores = adjustment_result['adjusted_scores']
            adjustments_made = adjustment_result['adjustments_made']

            # Step 7: Calculate final score
            logger.info("Step 6: Calculating final score...")
            if custom_weights:
                final_scorer = FinalScorer(custom_weights)
            else:
                final_scorer = self.final_scorer

            final_result = final_scorer.calculate_final_score(adjusted_scores)
            final_score = final_result['final_score']

            # Step 8: Generate summary
            logger.info("Step 7: Creating result...")
            summary = self._generate_basic_summary(
                ticker,
                final_score,
                adjusted_scores
            )

            # Step 9: Build result object
            result = self._build_result(
                ticker=ticker,
                final_score=final_score,
                category_results=category_results,
                adjusted_scores=adjusted_scores,
                metric_scores=metric_scores,
                summary=summary,
                adjustments_made=adjustments_made,
                peer_count=peer_count,
                stock_dict=stock_dict,
                percentiles=percentiles
            )

            logger.info(f"Successfully scored {ticker}: {final_score}/100")
            return result

        except Exception as e:
            logger.error(f"Error scoring {ticker}: {e}", exc_info=True)
            return None

    def _metrics_to_dict(self, metrics) -> Dict:
        return {
            'pe_ratio': metrics.pe_ratio,
            'peg_ratio': metrics.peg_ratio,
            'price_to_fcf': metrics.price_to_fcf,
            'revenue_growth': metrics.revenue_growth,
            'eps_growth': metrics.eps_growth,
            'roe': metrics.roe,
            'operating_margin': metrics.operating_margin,
            'net_margin': metrics.net_margin,
            'debt_to_equity': metrics.debt_to_equity,
            'current_ratio': metrics.current_ratio,
            'beta': metrics.beta,
        }

    def _get_all_metric_names(self) -> list:
        metric_names = []
        for category_metrics in METRICS.values():
            metric_names.extend(category_metrics.keys())
        return metric_names

    def _generate_basic_summary(
        self,
        ticker: str,
        final_score: float,
        category_scores: Dict[str, float]
    ) -> str:

        if final_score >= 80:
            rating = "Excellent"
        elif final_score >= 65:
            rating = "Good"
        elif final_score >= 50:
            rating = "Average"
        elif final_score >= 35:
            rating = "Below Average"
        else:
            rating = "Poor"

        best_category = max(
            category_scores.items(),
            key=lambda x: x[1] if x[1] is not None else 0
        )

        summary = (
            f"{ticker} receives a {rating.lower()} investment score "
            f"of {final_score}/100. "
            f"Strengths in {best_category[0]} "
            f"({best_category[1]:.0f}/100)."
        )

        return summary

    # ✅ RESTORED METHOD (this was missing)
    def _build_result(
        self,
        ticker: str,
        final_score: float,
        category_results: Dict,
        adjusted_scores: Dict,
        metric_scores: Dict,
        summary: str,
        adjustments_made: list,
        peer_count: int,
        stock_dict: Dict,
        percentiles: Dict
    ) -> ScoringResult:

        category_score_objects = {}

        for cat_name, cat_data in category_results.items():

            metric_score_objects = []

            for metric_info in cat_data.get('metrics', []):
                metric_name = metric_info['name']

                metric_score_obj = MetricScore(
                    metric_name=metric_name,
                    raw_value=stock_dict.get(metric_name),
                    percentile=percentiles.get(metric_name),
                    score=metric_info['score'],
                    peer_median=None
                )
                metric_score_objects.append(metric_score_obj)

            category_score_obj = CategoryScore(
                category=cat_name,
                score=adjusted_scores[cat_name],
                weight=self.final_scorer.category_weights[cat_name],
                metric_scores=metric_score_objects
            )

            category_score_objects[cat_name] = category_score_obj

        result = ScoringResult(
            ticker=ticker,
            final_score=final_score,
            category_scores=category_score_objects,
            strengths=[],
            weaknesses=[],
            warnings=adjustments_made,
            summary=summary,
            peer_count=peer_count,
            timestamp=datetime.now()
        )

        return result
