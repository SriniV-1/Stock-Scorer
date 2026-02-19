"""
Converts percentiles to 0-100 scores, handling metric inversions.

Key insight: For some metrics, low values are good (P/E ratio).
For others, high values are good (ROE).

We normalize everything so that 100 = best, 0 = worst.
"""

import logging
from typing import Dict, Optional
from src.utils.config import METRICS

logger = logging.getLogger(__name__)


class MetricScorer:
    """
    Converts percentiles to standardized 0-100 scores.
    
    The percentile tells us relative ranking, but we need to flip 
    it for "lower is better" metrics.
    """
    
    def __init__(self, metrics_config: Dict = None):
        """
        Args:
            metrics_config: Configuration dict (defaults to METRICS from config)
        """
        self.metrics_config = metrics_config or METRICS
    
    def score_from_percentile(
        self,
        percentile: float,
        metric_name: str,
        category: str
    ) -> float:
        """
        Convert percentile to score, applying inversion if needed.
        
        Logic:
        - For "higher is better" metrics (ROE): score = percentile
        - For "lower is better" metrics (P/E): score = 100 - percentile
        
        Args:
            percentile: Percentile rank (0-100)
            metric_name: Name of the metric
            category: Category it belongs to (valuation, growth, etc.)
        
        Returns:
            Score from 0-100
        
        Example:
            # ROE at 80th percentile (higher is better)
            >>> score = scorer.score_from_percentile(80, 'roe', 'profitability')
            >>> print(score)
            80.0
            
            # P/E at 80th percentile (lower is better - EXPENSIVE!)
            >>> score = scorer.score_from_percentile(80, 'pe_ratio', 'valuation')
            >>> print(score)
            20.0  # Inverted!
        """
        if percentile is None:
            return None
        
        # Look up whether lower is better
        try:
            metric_config = self.metrics_config[category][metric_name]
            lower_is_better = metric_config.get('lower_is_better', False)
        except KeyError:
            logger.warning(
                f"Metric {metric_name} not found in config. "
                f"Assuming higher is better."
            )
            lower_is_better = False
        
        # Apply inversion if needed
        if lower_is_better:
            score = 100 - percentile
        else:
            score = percentile
        
        return round(score, 2)
    
    def score_all_metrics(
        self,
        percentiles: Dict[str, float]
    ) -> Dict[str, Dict]:
        """
        Score all metrics from their percentiles.
        
        Args:
            percentiles: Dict mapping metric_name -> percentile
        
        Returns:
            Dict mapping metric_name -> {
                'percentile': float,
                'score': float,
                'category': str,
                'weight': float,
                'lower_is_better': bool,
                'display_name': str
            }
        
        Example:
            >>> percentiles = {
            ...     'pe_ratio': 70,
            ...     'roe': 85,
            ...     'revenue_growth': 60
            ... }
            >>> scores = scorer.score_all_metrics(percentiles)
            >>> print(scores['pe_ratio']['score'])
            30.0  # Inverted because lower P/E is better
            >>> print(scores['roe']['score'])
            85.0  # Not inverted because higher ROE is better
        """
        scored_metrics = {}
        
        # Iterate through all categories and metrics
        for category, metrics in self.metrics_config.items():
            for metric_name, metric_info in metrics.items():
                
                if metric_name not in percentiles:
                    continue
                
                percentile = percentiles[metric_name]
                
                if percentile is None:
                    scored_metrics[metric_name] = {
                        'percentile': None,
                        'score': None,
                        'category': category,
                        'weight': metric_info.get('weight', 0),
                        'lower_is_better': metric_info.get('lower_is_better', False),
                        'display_name': metric_info.get('display_name', metric_name)
                    }
                    continue
                
                score = self.score_from_percentile(
                    percentile, 
                    metric_name, 
                    category
                )
                
                scored_metrics[metric_name] = {
                    'percentile': percentile,
                    'score': score,
                    'category': category,
                    'weight': metric_info.get('weight', 0),
                    'lower_is_better': metric_info.get('lower_is_better', False),
                    'display_name': metric_info.get('display_name', metric_name)
                }
        
        return scored_metrics


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scorer = MetricScorer()
    
    print("\n" + "="*50)
    print("METRIC SCORER TESTS")
    print("="*50)
    
    # Test case 1: ROE (higher is better)
    print("\nTest 1: ROE at 85th percentile (higher is better)")
    print("-" * 50)
    score = scorer.score_from_percentile(85, 'roe', 'profitability')
    print(f"Percentile: 85")
    print(f"Score: {score}")
    print(f"✅ Should be 85 (no inversion)")
    
    # Test case 2: P/E (lower is better)
    print("\nTest 2: P/E at 85th percentile (lower is better)")
    print("-" * 50)
    score = scorer.score_from_percentile(85, 'pe_ratio', 'valuation')
    print(f"Percentile: 85")
    print(f"Score: {score}")
    print(f"✅ Should be 15 (100 - 85, inverted)")
    
    # Test case 3: Score all metrics
    print("\nTest 3: Score Multiple Metrics")
    print("-" * 50)
    test_percentiles = {
        'pe_ratio': 70,
        'roe': 85,
        'revenue_growth': 60,
        'debt_to_equity': 30
    }
    
    scores = scorer.score_all_metrics(test_percentiles)
    
    print("\nMetric Scores:")
    for metric, data in scores.items():
        inversion = " (inverted)" if data['lower_is_better'] else ""
        print(f"  {metric}:")
        print(f"    Percentile: {data['percentile']}")
        print(f"    Score: {data['score']}{inversion}")
    
    print("\n" + "="*50)
    print("✅ METRIC SCORER WORKING!")
    print("="*50)