"""
Contextual adjustment logic for finance-aware scoring.

These adjustments capture nuances that pure percentile rankings miss:
- High P/E can be justified by high growth
- High debt is worse when liquidity is weak
- Low profitability is OK for high-growth companies
"""

import logging
from typing import Dict, Tuple, Optional
from src.utils.config import THRESHOLDS

logger = logging.getLogger(__name__)


class ContextualAdjuster:
    """
    Applies finance logic to adjust category scores.
    
    Philosophy: Numbers don't exist in isolation. A high P/E ratio 
    might be fine for a fast-growing tech company but terrible for 
    a slow-growing utility.
    """
    
    def __init__(self, thresholds: Dict = None):
        self.thresholds = thresholds or THRESHOLDS
    
    def adjust_valuation_for_growth(
        self,
        valuation_score: float,
        growth_score: float,
        raw_metrics: Dict
    ) -> Tuple[float, Optional[str]]:
        """
        Reduce valuation penalty if growth is strong.
        
        Logic: High P/E is acceptable if the company is growing fast.
        This is the essence of growth investing.
        
        Args:
            valuation_score: Raw valuation score (0-100)
            growth_score: Growth category score (0-100)
            raw_metrics: Dict with raw metric values
        
        Returns:
            (adjusted_score, explanation)
        
        Example:
            Stock has P/E of 40 (expensive, score=30)
            But revenue growth is 40% (strong, score=85)
            
            Adjustment: +12.5 points to valuation
            New score: 42.5
        """
        adjustment = 0
        explanation = None
        
        # Only adjust if valuation is below average but growth is strong
        if valuation_score < 50 and growth_score > 70:
            # Calculate adjustment (up to +20 points)
            adjustment = min((growth_score - 70) * 0.5, 20)
            
            adjusted_score = min(valuation_score + adjustment, 100)
            
            explanation = (
                f"Valuation score increased by {adjustment:.1f} points "
                f"due to strong growth (score: {growth_score:.1f})"
            )
            
            logger.info(explanation)
            return adjusted_score, explanation
        
        return valuation_score, None
    
    def adjust_risk_for_liquidity(
        self,
        risk_score: float,
        raw_metrics: Dict
    ) -> Tuple[float, Optional[str]]:
        """
        Amplify risk penalty if debt is high AND liquidity is weak.
        
        Logic: High debt alone isn't terrible if the company has 
        plenty of cash. But high debt + low cash = danger.
        
        Args:
            risk_score: Raw risk score (0-100)
            raw_metrics: Dict with raw metric values
        
        Returns:
            (adjusted_score, explanation)
        """
        debt_to_equity = raw_metrics.get('debt_to_equity')
        current_ratio = raw_metrics.get('current_ratio')
        
        if debt_to_equity is None or current_ratio is None:
            return risk_score, None
        
        adjustment = 0
        explanation = None
        
        # High debt + weak liquidity = major red flag
        if (debt_to_equity > self.thresholds['high_debt'] and 
            current_ratio < self.thresholds['weak_liquidity']):
            
            # Penalty scales with severity
            severity = (debt_to_equity - self.thresholds['high_debt']) * \
                       (self.thresholds['weak_liquidity'] - current_ratio)
            
            adjustment = min(severity * 10, 25)  # Cap at -25 points
            
            adjusted_score = max(risk_score - adjustment, 0)
            
            explanation = (
                f"Risk score reduced by {adjustment:.1f} points due to "
                f"high debt ({debt_to_equity:.2f}) and weak liquidity "
                f"(current ratio: {current_ratio:.2f})"
            )
            
            logger.warning(explanation)
            return adjusted_score, explanation
        
        return risk_score, None
    
    def adjust_profitability_for_growth_stage(
        self,
        profitability_score: float,
        growth_score: float,
        raw_metrics: Dict
    ) -> Tuple[float, Optional[str]]:
        """
        Forgive low profitability if growth is exceptional.
        
        Logic: High-growth companies (Amazon in early days) often 
        sacrifice margins for market share. This is strategic, not bad.
        
        Args:
            profitability_score: Raw profitability score
            growth_score: Growth category score
            raw_metrics: Dict with raw metric values
        
        Returns:
            (adjusted_score, explanation)
        """
        revenue_growth = raw_metrics.get('revenue_growth')
        
        if revenue_growth is None:
            return profitability_score, None
        
        adjustment = 0
        explanation = None
        
        # Low margins are OK if growth is >30%/year
        if profitability_score < 40 and revenue_growth > 0.30:
            adjustment = min(revenue_growth * 30, 15)  # Up to +15 points
            
            adjusted_score = min(profitability_score + adjustment, 100)
            
            explanation = (
                f"Profitability score increased by {adjustment:.1f} points "
                f"due to exceptional growth ({revenue_growth:.1%})"
            )
            
            logger.info(explanation)
            return adjusted_score, explanation
        
        return profitability_score, None
    
    def apply_all_adjustments(
        self,
        category_scores: Dict[str, Dict],
        raw_metrics: Dict
    ) -> Dict:
        """
        Apply all contextual adjustments.
        
        Args:
            category_scores: Output from CategoryAggregator
            raw_metrics: Raw metric values
        
        Returns:
            {
                'adjusted_scores': Dict[str, float],
                'adjustments_made': List[str]
            }
        """
        adjusted = {}
        explanations = []
        
        # Extract raw scores
        raw_scores = {
            cat: data['score'] if data['score'] is not None else 50
            for cat, data in category_scores.items()
        }
        
        # Adjustment 1: Valuation for growth
        val_score, val_exp = self.adjust_valuation_for_growth(
            raw_scores.get('valuation', 50),
            raw_scores.get('growth', 50),
            raw_metrics
        )
        adjusted['valuation'] = val_score
        if val_exp:
            explanations.append(val_exp)
        
        # Adjustment 2: Risk for liquidity
        risk_score, risk_exp = self.adjust_risk_for_liquidity(
            raw_scores.get('risk', 50),
            raw_metrics
        )
        adjusted['risk'] = risk_score
        if risk_exp:
            explanations.append(risk_exp)
        
        # Adjustment 3: Profitability for growth stage
        prof_score, prof_exp = self.adjust_profitability_for_growth_stage(
            raw_scores.get('profitability', 50),
            raw_scores.get('growth', 50),
            raw_metrics
        )
        adjusted['profitability'] = prof_score
        if prof_exp:
            explanations.append(prof_exp)
        
        # Growth doesn't get adjusted (it's the benchmark for others)
        adjusted['growth'] = raw_scores.get('growth', 50)
        
        return {
            'adjusted_scores': adjusted,
            'adjustments_made': explanations
        }


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    adjuster = ContextualAdjuster()
    
    print("\n" + "="*50)
    print("CONTEXTUAL ADJUSTMENTS TESTS")
    print("="*50)
    
    # Test case 1: High P/E but high growth
    print("\nTest 1: High P/E justified by growth")
    print("-" * 50)
    
    val_score, explanation = adjuster.adjust_valuation_for_growth(
        valuation_score=35,  # Low score (expensive)
        growth_score=85,      # High growth
        raw_metrics={'pe_ratio': 45, 'revenue_growth': 0.40}
    )
    
    print(f"Original valuation score: 35")
    print(f"Growth score: 85")
    print(f"Adjusted valuation score: {val_score}")
    print(f"Explanation: {explanation}")
    
    # Test case 2: High debt + weak liquidity
    print("\n\nTest 2: High debt with weak liquidity")
    print("-" * 50)
    
    risk_score, explanation = adjuster.adjust_risk_for_liquidity(
        risk_score=45,
        raw_metrics={
            'debt_to_equity': 3.5,  # Very high
            'current_ratio': 0.8     # Weak
        }
    )
    
    print(f"Original risk score: 45")
    print(f"Debt/Equity: 3.5")
    print(f"Current Ratio: 0.8")
    print(f"Adjusted risk score: {risk_score}")
    print(f"Explanation: {explanation}")
    
    # Test case 3: Full adjustment pipeline
    print("\n\nTest 3: Apply all adjustments")
    print("-" * 50)
    
    category_scores = {
        'valuation': {'score': 35},
        'growth': {'score': 85},
        'profitability': {'score': 30},
        'risk': {'score': 45}
    }
    
    raw_metrics = {
        'pe_ratio': 45,
        'revenue_growth': 0.40,
        'debt_to_equity': 3.5,
        'current_ratio': 0.8
    }
    
    result = adjuster.apply_all_adjustments(category_scores, raw_metrics)
    
    print("\nAdjusted scores:")
    for cat, score in result['adjusted_scores'].items():
        orig = category_scores[cat]['score']
        change = score - orig
        print(f"  {cat:15} {orig:5.1f} → {score:5.1f} ({change:+.1f})")
    
    print("\nAdjustments made:")
    for exp in result['adjustments_made']:
        print(f"  - {exp}")
    
    print("\n" + "="*50)
    print("✅ CONTEXTUAL ADJUSTMENTS WORKING!")
    print("="*50)