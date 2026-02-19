"""
Aggregates individual metric scores into category scores.

Process:
1. Group metrics by category (valuation, growth, etc.)
2. Calculate weighted average within each category
3. Handle missing metrics by redistributing weights
"""

import logging
from typing import Dict, List
from src.utils.config import METRICS, CATEGORY_WEIGHTS

logger = logging.getLogger(__name__)


class CategoryAggregator:
    """
    Combines metric scores into category scores using weighted averages.
    
    Example:
        Valuation category has 3 metrics:
        - P/E (weight=0.4, score=60)
        - PEG (weight=0.35, score=70)
        - Price/FCF (weight=0.25, score=50)
        
        Category score = 0.4*60 + 0.35*70 + 0.25*50 = 61.0
    """
    
    def __init__(self, metrics_config: Dict = None):
        self.metrics_config = metrics_config or METRICS
    
    def aggregate_category(
        self,
        category: str,
        metric_scores: Dict[str, Dict]
    ) -> Dict:
        """
        Calculate weighted average score for a category.
        
        Args:
            category: Category name ('valuation', 'growth', etc.)
            metric_scores: Dict from score_all_metrics()
        
        Returns:
            {
                'score': float,
                'metrics': List of metric details,
                'missing_metrics': List of missing metric names
            }
        """
        category_config = self.metrics_config.get(category, {})
        
        if not category_config:
            logger.error(f"Unknown category: {category}")
            return {'score': None, 'metrics': [], 'missing_metrics': []}
        
        # Separate available and missing metrics
        available_metrics = []
        missing_metrics = []
        
        for metric_name, metric_config in category_config.items():
            metric_data = metric_scores.get(metric_name)
            
            if metric_data and metric_data.get('score') is not None:
                # Ensure weight is a float
                weight = metric_config.get('weight', 0)
                try:
                    weight = float(weight)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid weight for {metric_name}, using 0")
                    weight = 0.0
                
                available_metrics.append({
                    'name': metric_name,
                    'score': float(metric_data['score']),
                    'weight': weight,
                    'percentile': metric_data.get('percentile'),
                    'display_name': metric_config.get('display_name', metric_name)
                })
            else:
                missing_metrics.append(metric_name)
        
        # Handle case where no metrics are available
        if not available_metrics:
            logger.warning(f"No valid metrics for category: {category}")
            return {
                'score': None,
                'metrics': [],
                'missing_metrics': missing_metrics
            }
        
        # Redistribute weights if some metrics are missing
        total_available_weight = sum(m['weight'] for m in available_metrics)
        
        if total_available_weight == 0:
            logger.error(f"Total weight is 0 for category {category}")
            return {
                'score': None,
                'metrics': available_metrics,
                'missing_metrics': missing_metrics
            }
        
        for metric in available_metrics:
            # Normalize weight so they sum to 1.0
            metric['adjusted_weight'] = metric['weight'] / total_available_weight
        
        # Calculate weighted average
        category_score = sum(
            m['score'] * m['adjusted_weight'] 
            for m in available_metrics
        )
        
        return {
            'score': round(category_score, 2),
            'metrics': available_metrics,
            'missing_metrics': missing_metrics
        }
    
    def aggregate_all_categories(
        self,
        metric_scores: Dict[str, Dict]
    ) -> Dict[str, Dict]:
        """
        Aggregate all categories.
        
        Returns:
            Dict mapping category -> aggregation result
        """
        category_scores = {}
        
        for category in self.metrics_config.keys():
            category_scores[category] = self.aggregate_category(
                category, 
                metric_scores
            )
        
        return category_scores


# Testing
if __name__ == "__main__":
    from src.scoring.metric_scorer import MetricScorer
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*50)
    print("CATEGORY AGGREGATOR TESTS")
    print("="*50)
    
    # Create sample percentiles
    percentiles = {
        'pe_ratio': 70,
        'peg_ratio': 65,
        'price_to_fcf': 75,
        'roe': 85,
        'operating_margin': 80,
        'net_margin': 75,
        'revenue_growth': 60,
        'eps_growth': 55,
        'debt_to_equity': 30,
        'current_ratio': 70,
        'beta': 40
    }
    
    # Score metrics
    print("\nStep 1: Scoring metrics...")
    scorer = MetricScorer()
    metric_scores = scorer.score_all_metrics(percentiles)
    
    # Aggregate categories
    print("Step 2: Aggregating categories...")
    aggregator = CategoryAggregator()
    category_scores = aggregator.aggregate_all_categories(metric_scores)
    
    print("\n" + "-"*50)
    print("CATEGORY SCORES:")
    print("-"*50)
    
    for category, data in category_scores.items():
        print(f"\n{category.upper()}: {data['score']:.1f}/100")
        print("  Metrics:")
        for m in data['metrics']:
            print(f"    - {m['display_name']}: {m['score']:.1f} "
                  f"(weight: {m['adjusted_weight']:.2%})")
        
        if data['missing_metrics']:
            print(f"  Missing: {data['missing_metrics']}")
    
    print("\n" + "="*50)
    print("✅ CATEGORY AGGREGATOR WORKING!")
    print("="*50)