"""
Calculates the final 0-100 investment score.

This ties everything together:
1. Category scores (adjusted)
2. Category weights
3. Final weighted average
"""

import logging
from typing import Dict
from src.utils.config import CATEGORY_WEIGHTS

logger = logging.getLogger(__name__)


class FinalScorer:
    """
    Computes the final investment score from category scores.
    
    Formula:
        Final Score = Σ (category_weight × category_score)
    
    Example:
        Valuation: 60 (weight: 0.30) → contributes 18 points
        Growth: 80 (weight: 0.25) → contributes 20 points
        Profitability: 70 (weight: 0.25) → contributes 17.5 points
        Risk: 50 (weight: 0.20) → contributes 10 points
        
        Final Score = 18 + 20 + 17.5 + 10 = 65.5
    """
    
    def __init__(self, category_weights: Dict[str, float] = None):
        """
        Args:
            category_weights: Dict mapping category -> weight
                              Must sum to 1.0
        """
        self.category_weights = category_weights or CATEGORY_WEIGHTS
        
        # Validate weights sum to 1.0
        total_weight = sum(self.category_weights.values())
        if not 0.99 <= total_weight <= 1.01:  # Allow floating point error
            logger.warning(
                f"Category weights sum to {total_weight}, not 1.0. "
                f"Normalizing..."
            )
            # Normalize weights
            for cat in self.category_weights:
                self.category_weights[cat] /= total_weight
    
    def calculate_final_score(
        self,
        category_scores: Dict[str, float]
    ) -> Dict:
        """
        Calculate weighted average of category scores.
        
        Args:
            category_scores: Dict mapping category -> score
        
        Returns:
            {
                'final_score': float,
                'breakdown': Dict with contribution details,
                'warnings': List of warnings
            }
        """
        weighted_sum = 0
        breakdown = {}
        warnings = []
        total_weight_used = 0
        
        for category, weight in self.category_weights.items():
            score = category_scores.get(category)
            
            if score is None:
                warnings.append(
                    f"Missing score for {category}. "
                    f"Using 50 (neutral) as default."
                )
                score = 50
            
            contribution = weight * score
            weighted_sum += contribution
            total_weight_used += weight
            
            breakdown[category] = {
                'score': score,
                'weight': weight,
                'contribution': contribution
            }
        
        # Normalize if some categories were missing
        if total_weight_used < 0.99:
            weighted_sum = weighted_sum / total_weight_used
            warnings.append(
                f"Only {total_weight_used:.1%} of weight available. "
                f"Score normalized."
            )
        
        final_score = round(weighted_sum, 1)
        
        return {
            'final_score': final_score,
            'breakdown': breakdown,
            'warnings': warnings
        }
    
    def interpret_score(self, score: float) -> Dict:
        """
        Provide interpretation of the final score.
        
        Args:
            score: Final score (0-100)
        
        Returns:
            {
                'rating': str,
                'description': str,
                'action': str
            }
        """
        if score >= 80:
            return {
                'rating': 'Excellent',
                'description': 'Strong fundamentals across all categories',
                'action': 'Strong buy candidate - consider for portfolio'
            }
        elif score >= 65:
            return {
                'rating': 'Good',
                'description': 'Solid fundamentals with some strengths',
                'action': 'Buy candidate - monitor key metrics'
            }
        elif score >= 50:
            return {
                'rating': 'Average',
                'description': 'Mixed fundamentals',
                'action': 'Hold or further research - compare alternatives'
            }
        elif score >= 35:
            return {
                'rating': 'Below Average',
                'description': 'Concerning fundamentals',
                'action': 'Avoid unless deep value opportunity'
            }
        else:
            return {
                'rating': 'Poor',
                'description': 'Weak fundamentals across categories',
                'action': 'Avoid - high risk of underperformance'
            }


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scorer = FinalScorer()
    
    print("\n" + "="*50)
    print("FINAL SCORER TESTS")
    print("="*50)
    
    # Test case 1: All categories present
    print("\nTest 1: Complete category scores")
    print("-" * 50)
    
    category_scores = {
        'valuation': 60,
        'growth': 80,
        'profitability': 70,
        'risk': 50
    }
    
    result = scorer.calculate_final_score(category_scores)
    
    print(f"Final Score: {result['final_score']}\n")
    print("Breakdown:")
    for cat, data in result['breakdown'].items():
        print(f"  {cat:15}")
        print(f"    Score: {data['score']:5.1f}")
        print(f"    Weight: {data['weight']:.1%}")
        print(f"    Contribution: {data['contribution']:5.2f}")
    
    interpretation = scorer.interpret_score(result['final_score'])
    print(f"\nRating: {interpretation['rating']}")
    print(f"Description: {interpretation['description']}")
    print(f"Action: {interpretation['action']}")
    
    # Test case 2: Missing category
    print("\n\nTest 2: Missing growth score")
    print("-" * 50)
    
    incomplete_scores = {
        'valuation': 60,
        'profitability': 70,
        'risk': 50
    }
    
    result = scorer.calculate_final_score(incomplete_scores)
    print(f"Final Score: {result['final_score']}")
    
    if result['warnings']:
        print("\nWarnings:")
        for warning in result['warnings']:
            print(f"  - {warning}")
    
    # Test case 3: Different score ranges
    print("\n\nTest 3: Score Interpretations")
    print("-" * 50)
    
    test_scores = [95, 75, 55, 40, 25]
    
    for test_score in test_scores:
        interp = scorer.interpret_score(test_score)
        print(f"Score {test_score:3d}: {interp['rating']:15} - {interp['action']}")
    
    print("\n" + "="*50)
    print("✅ FINAL SCORER WORKING!")
    print("="*50)
