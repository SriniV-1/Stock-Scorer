"""
Natural language explanation generator.

Converts numeric scores into human-readable insights:
- Strengths (high-scoring metrics)
- Weaknesses (low-scoring metrics)
- Warnings (concerning patterns)
- Overall summary
"""

import logging
from typing import Dict, List
from src.utils.config import METRICS, THRESHOLDS

logger = logging.getLogger(__name__)


class ExplanationEngine:
    """
    Generates natural language explanations for scoring results.
    
    Philosophy: Numbers are meaningless without context. 
    We translate scores into actionable insights.
    """
    
    def __init__(self):
        self.metrics_config = METRICS
        self.thresholds = THRESHOLDS
    
    def generate_explanation(
        self,
        ticker: str,
        final_score: float,
        category_scores: Dict[str, float],
        metric_scores: Dict[str, Dict],
        raw_metrics: Dict,
        adjustments: List[str] = None
    ) -> Dict:
        """
        Generate complete explanation.
        
        Returns:
            {
                'strengths': List[str],
                'weaknesses': List[str],
                'warnings': List[str],
                'summary': str
            }
        """
        strengths = self._identify_strengths(metric_scores, raw_metrics)
        weaknesses = self._identify_weaknesses(metric_scores, raw_metrics)
        warnings = self._generate_warnings(raw_metrics, adjustments)
        summary = self._generate_summary(ticker, final_score, category_scores)
        
        return {
            'strengths': strengths,
            'weaknesses': weaknesses,
            'warnings': warnings,
            'summary': summary
        }
    
    def _identify_strengths(
        self,
        metric_scores: Dict[str, Dict],
        raw_metrics: Dict
    ) -> List[str]:
        """
        Identify top-performing metrics (score > 70).
        
        Returns list of strength descriptions.
        """
        strengths = []
        
        # Sort metrics by score
        scored_metrics = [
            (name, data) 
            for name, data in metric_scores.items() 
            if data.get('score') is not None
        ]
        scored_metrics.sort(key=lambda x: x[1]['score'], reverse=True)
        
        # Take top metrics with score > 70
        for metric_name, metric_data in scored_metrics[:5]:
            score = metric_data['score']
            
            if score > 70:
                raw_value = raw_metrics.get(metric_name)
                percentile = metric_data.get('percentile')
                display_name = metric_data.get('display_name', metric_name)
                
                # Generate description
                description = self._format_strength(
                    display_name,
                    raw_value,
                    score,
                    percentile
                )
                
                if description:
                    strengths.append(description)
        
        return strengths
    
    def _identify_weaknesses(
        self,
        metric_scores: Dict[str, Dict],
        raw_metrics: Dict
    ) -> List[str]:
        """
        Identify poor-performing metrics (score < 40).
        
        Returns list of weakness descriptions.
        """
        weaknesses = []
        
        # Sort metrics by score (ascending)
        scored_metrics = [
            (name, data) 
            for name, data in metric_scores.items() 
            if data.get('score') is not None
        ]
        scored_metrics.sort(key=lambda x: x[1]['score'])
        
        # Take bottom metrics with score < 40
        for metric_name, metric_data in scored_metrics[:5]:
            score = metric_data['score']
            
            if score < 40:
                raw_value = raw_metrics.get(metric_name)
                percentile = metric_data.get('percentile')
                display_name = metric_data.get('display_name', metric_name)
                
                # Generate description
                description = self._format_weakness(
                    display_name,
                    raw_value,
                    score,
                    percentile
                )
                
                if description:
                    weaknesses.append(description)
        
        return weaknesses
    
    def _format_strength(
        self,
        metric_name: str,
        raw_value: float,
        score: float,
        percentile: float
    ) -> str:
        """Format a strength description"""
        
        if raw_value is None:
            return None
        
        if percentile and percentile >= 80:
            rank = "top 20%"
        elif percentile and percentile >= 70:
            rank = "top 30%"
        else:
            rank = "above average"
        
        # Format value based on metric type
        if metric_name in ['ROE', 'Operating Margin', 'Net Margin']:
            value_str = f"{raw_value:.1%}"
        elif metric_name in ['Revenue Growth', 'EPS Growth']:
            value_str = f"{raw_value:.1%}"
        elif metric_name in ['P/E Ratio', 'PEG Ratio', 'Price/FCF']:
            value_str = f"{raw_value:.1f}"
        elif metric_name in ['Debt/Equity', 'Current Ratio', 'Beta']:
            value_str = f"{raw_value:.2f}"
        else:
            value_str = f"{raw_value:.2f}"
        
        return f"Strong {metric_name.lower()} of {value_str} ({rank} of peers)"
    
    def _format_weakness(
        self,
        metric_name: str,
        raw_value: float,
        score: float,
        percentile: float
    ) -> str:
        """Format a weakness description"""
        
        if raw_value is None:
            return None
        
        if percentile and percentile <= 20:
            rank = "bottom 20%"
        elif percentile and percentile <= 30:
            rank = "bottom 30%"
        else:
            rank = "below average"
        
        # Format value
        if metric_name in ['ROE', 'Operating Margin', 'Net Margin']:
            value_str = f"{raw_value:.1%}"
        elif metric_name in ['Revenue Growth', 'EPS Growth']:
            value_str = f"{raw_value:.1%}"
        elif metric_name in ['P/E Ratio', 'PEG Ratio', 'Price/FCF']:
            value_str = f"{raw_value:.1f}"
        elif metric_name in ['Debt/Equity', 'Current Ratio', 'Beta']:
            value_str = f"{raw_value:.2f}"
        else:
            value_str = f"{raw_value:.2f}"
        
        return f"Weak {metric_name.lower()} of {value_str} ({rank} of peers)"
    
    def _generate_warnings(
        self,
        raw_metrics: Dict,
        adjustments: List[str] = None
    ) -> List[str]:
        """
        Generate warnings for concerning patterns.
        """
        warnings = []
        
        # Warning 1: High debt + weak liquidity
        debt = raw_metrics.get('debt_to_equity')
        current_ratio = raw_metrics.get('current_ratio')
        
        if debt and current_ratio:
            if debt > self.thresholds['high_debt'] and current_ratio < self.thresholds['weak_liquidity']:
                warnings.append(
                    f"⚠️ High leverage concern: Debt/Equity of {debt:.1f} "
                    f"with current ratio of {current_ratio:.2f}"
                )
        
        # Warning 2: Negative growth
        revenue_growth = raw_metrics.get('revenue_growth')
        if revenue_growth and revenue_growth < self.thresholds['negative_growth']:
            warnings.append(
                f"⚠️ Revenue declining: {revenue_growth:.1%} year-over-year"
            )
        
        # Warning 3: Extreme P/E
        pe_ratio = raw_metrics.get('pe_ratio')
        if pe_ratio and pe_ratio > self.thresholds['extreme_pe']:
            warnings.append(
                f"⚠️ Extreme valuation: P/E ratio of {pe_ratio:.1f} may indicate data issues or unprofitability"
            )
        elif pe_ratio and pe_ratio < 0:
            warnings.append(
                f"⚠️ Negative P/E ratio indicates company is unprofitable"
            )
        
        # Add adjustment notes
        if adjustments:
            for adj in adjustments:
                warnings.append(f"ℹ️ {adj}")
        
        return warnings
    
    def _generate_summary(
        self,
        ticker: str,
        final_score: float,
        category_scores: Dict[str, float]
    ) -> str:
        """
        Generate 1-2 sentence summary.
        """
        # Determine rating
        if final_score >= 80:
            rating = "excellent"
            action = "Strong buy candidate"
        elif final_score >= 65:
            rating = "good"
            action = "Buy candidate"
        elif final_score >= 50:
            rating = "average"
            action = "Hold or research further"
        elif final_score >= 35:
            rating = "below average"
            action = "Proceed with caution"
        else:
            rating = "poor"
            action = "High risk"
        
        # Find best and worst categories
        valid_categories = {
            k: v for k, v in category_scores.items() 
            if v is not None
        }
        
        if valid_categories:
            best_cat = max(valid_categories.items(), key=lambda x: x[1])
            worst_cat = min(valid_categories.items(), key=lambda x: x[1])
            
            summary = (
                f"{ticker} receives a {rating} investment score of {final_score:.1f}/100. "
                f"{action}. Strongest in {best_cat[0]} ({best_cat[1]:.0f}/100), "
                f"weakest in {worst_cat[0]} ({worst_cat[1]:.0f}/100)."
            )
        else:
            summary = f"{ticker} receives a {rating} investment score of {final_score:.1f}/100. {action}."
        
        return summary


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    explainer = ExplanationEngine()
    
    print("\n" + "="*70)
    print("EXPLANATION ENGINE TEST")
    print("="*70)
    
    # Mock data
    metric_scores = {
        'pe_ratio': {
            'score': 30,
            'percentile': 70,
            'display_name': 'P/E Ratio'
        },
        'roe': {
            'score': 85,
            'percentile': 85,
            'display_name': 'ROE'
        },
        'revenue_growth': {
            'score': 75,
            'percentile': 75,
            'display_name': 'Revenue Growth'
        },
        'debt_to_equity': {
            'score': 20,
            'percentile': 80,
            'display_name': 'Debt/Equity'
        }
    }
    
    raw_metrics = {
        'pe_ratio': 35,
        'roe': 0.25,
        'revenue_growth': 0.15,
        'debt_to_equity': 3.5,
        'current_ratio': 0.9
    }
    
    category_scores = {
        'valuation': 40,
        'growth': 75,
        'profitability': 85,
        'risk': 30
    }
    
    adjustments = [
        "Valuation score adjusted for strong growth"
    ]
    
    # Generate explanation
    explanation = explainer.generate_explanation(
        ticker='TEST',
        final_score=60,
        category_scores=category_scores,
        metric_scores=metric_scores,
        raw_metrics=raw_metrics,
        adjustments=adjustments
    )
    
    print("\n📊 SUMMARY:")
    print(explanation['summary'])
    
    print("\n✅ STRENGTHS:")
    for strength in explanation['strengths']:
        print(f"  • {strength}")
    
    print("\n❌ WEAKNESSES:")
    for weakness in explanation['weaknesses']:
        print(f"  • {weakness}")
    
    print("\n⚠️  WARNINGS:")
    for warning in explanation['warnings']:
        print(f"  • {warning}")
    
    print("\n" + "="*70)
    print("✅ EXPLANATION ENGINE WORKING!")
    print("="*70)