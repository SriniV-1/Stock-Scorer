"""
Backtesting framework to validate scoring system.

Goal: Test if our scores predict future returns.

Process:
1. Score stocks at time T
2. Measure returns from T to T+N months
3. Analyze correlation between scores and returns
4. Identify which categories are most predictive
"""

import pandas as pd
import numpy as np
from typing import Dict, List
from datetime import datetime, timedelta
import logging

from src.scoring.engine import StockScoringEngine
from src.data.api_client import YahooFinanceClient

logger = logging.getLogger(__name__)


class Backtester:
    """
    Backtests the scoring system against historical returns.
    
    Key metrics:
    - Correlation between score and forward returns
    - Top quartile vs bottom quartile performance
    - Hit rate (% of high scores that outperform)
    """
    
    def __init__(self):
        self.engine = StockScoringEngine()
        self.client = YahooFinanceClient()
    
    def backtest_stocks(
        self,
        tickers: List[str],
        lookback_months: int = 12,
        forward_months: int = 6
    ) -> pd.DataFrame:
        """
        Backtest scoring system on a list of stocks.
        
        Args:
            tickers: List of stock symbols
            lookback_months: How far back to score stocks
            forward_months: How far forward to measure returns
        
        Returns:
            DataFrame with scores and forward returns
        """
        results = []
        
        # Calculate date range
        score_date = datetime.now() - timedelta(days=lookback_months * 30)
        return_end_date = score_date + timedelta(days=forward_months * 30)
        
        logger.info(f"Backtesting {len(tickers)} stocks")
        logger.info(f"Score date: {score_date.date()}")
        logger.info(f"Return period: {score_date.date()} to {return_end_date.date()}")
        
        for ticker in tickers:
            logger.info(f"Processing {ticker}...")
            
            try:
                # Score the stock (using current data as proxy)
                scoring_result = self.engine.score_stock(ticker)
                
                if not scoring_result:
                    logger.warning(f"Failed to score {ticker}")
                    continue
                
                # Calculate forward returns
                forward_return = self._calculate_forward_return(
                    ticker,
                    score_date.strftime('%Y-%m-%d'),
                    return_end_date.strftime('%Y-%m-%d')
                )
                
                if forward_return is None:
                    logger.warning(f"Failed to get returns for {ticker}")
                    continue
                
                # Extract category scores
                category_scores = {
                    cat_name: cat_obj.score
                    for cat_name, cat_obj in scoring_result.category_scores.items()
                }
                
                result_row = {
                    'ticker': ticker,
                    'score_date': score_date,
                    'final_score': scoring_result.final_score,
                    'forward_return': forward_return,
                    **{f'{cat}_score': score for cat, score in category_scores.items()}
                }
                
                results.append(result_row)
                
                logger.info(
                    f"  {ticker}: Score={scoring_result.final_score:.1f}, "
                    f"Return={forward_return:.1%}"
                )
            
            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                continue
        
        df = pd.DataFrame(results)
        return df
    
    def _calculate_forward_return(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> float:
        """
        Calculate total return over a period.
        
        Returns:
            Decimal return (e.g., 0.15 for 15% return)
        """
        try:
            hist = self.client.get_historical_price_data(
                ticker,
                start_date,
                end_date
            )
            
            if hist.empty:
                return None
            
            start_price = hist['Close'].iloc[0]
            end_price = hist['Close'].iloc[-1]
            
            total_return = (end_price - start_price) / start_price
            
            return total_return
        
        except Exception as e:
            logger.error(f"Error calculating return for {ticker}: {e}")
            return None
    
    def analyze_results(self, backtest_df: pd.DataFrame) -> Dict:
        """
        Analyze backtest results.
        
        Returns:
            Dict with analysis metrics
        """
        if backtest_df.empty:
            logger.error("Empty backtest results")
            return {}
        
        analysis = {}
        
        # Overall correlation
        correlation = backtest_df['final_score'].corr(backtest_df['forward_return'])
        analysis['score_return_correlation'] = correlation
        
        # Quartile analysis
        q75 = backtest_df['final_score'].quantile(0.75)
        q25 = backtest_df['final_score'].quantile(0.25)
        
        top_quartile = backtest_df[backtest_df['final_score'] >= q75]
        bottom_quartile = backtest_df[backtest_df['final_score'] <= q25]
        
        analysis['top_quartile_avg_return'] = top_quartile['forward_return'].mean()
        analysis['bottom_quartile_avg_return'] = bottom_quartile['forward_return'].mean()
        analysis['top_vs_bottom_spread'] = (
            analysis['top_quartile_avg_return'] - 
            analysis['bottom_quartile_avg_return']
        )
        
        # Hit rate
        high_score = backtest_df[backtest_df['final_score'] >= 65]
        if len(high_score) > 0:
            hit_rate = (high_score['forward_return'] > 0).mean()
            analysis['high_score_hit_rate'] = hit_rate
        else:
            analysis['high_score_hit_rate'] = None
        
        # Category correlations
        category_cols = [col for col in backtest_df.columns if col.endswith('_score')]
        category_correlations = {}
        
        for col in category_cols:
            cat_name = col.replace('_score', '')
            corr = backtest_df[col].corr(backtest_df['forward_return'])
            category_correlations[cat_name] = corr
        
        analysis['category_correlations'] = category_correlations
        
        # Most predictive category
        if category_correlations:
            best_cat = max(category_correlations.items(), key=lambda x: abs(x[1]))
            analysis['most_predictive_category'] = best_cat[0]
            analysis['most_predictive_correlation'] = best_cat[1]
        
        return analysis
    
    def generate_report(self, backtest_df: pd.DataFrame) -> str:
        """Generate a human-readable backtest report."""
        
        analysis = self.analyze_results(backtest_df)
        
        if not analysis:
            return "No analysis results available"
        
        report = []
        report.append("=" * 70)
        report.append("BACKTEST REPORT")
        report.append("=" * 70)
        report.append(f"Stocks analyzed: {len(backtest_df)}")
        report.append("")
        
        report.append("OVERALL PERFORMANCE")
        report.append("-" * 70)
        report.append(
            f"Correlation (Score vs Returns): "
            f"{analysis['score_return_correlation']:.3f}"
        )
        
        report.append("")
        report.append("QUARTILE ANALYSIS")
        report.append("-" * 70)
        report.append(
            f"Top quartile avg return:    "
            f"{analysis['top_quartile_avg_return']:.2%}"
        )
        report.append(
            f"Bottom quartile avg return: "
            f"{analysis['bottom_quartile_avg_return']:.2%}"
        )
        
        if analysis.get('high_score_hit_rate'):
            report.append("")
            report.append("HIT RATE")
            report.append("-" * 70)
            report.append(
                f"High-score stocks (≥65) with positive returns: "
                f"{analysis['high_score_hit_rate']:.1%}"
            )
        
        report_text = "\n".join(report)
        return report_text


# Testing
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    backtester = Backtester()
    
    print("\n" + "="*70)
    print("BACKTESTER TEST")
    print("="*70)
    
    # Small test
    test_stocks = ['AAPL', 'MSFT', 'GOOGL']
    
    print(f"\nBacktesting {len(test_stocks)} stocks...")
    print("(This will take a few minutes...)\n")
    
    results = backtester.backtest_stocks(
        test_stocks,
        lookback_months=12,
        forward_months=6
    )
    
    if not results.empty:
        report = backtester.generate_report(results)
        print("\n" + report)
        
        print("\n" + "="*70)
        print("✅ BACKTESTER WORKING!")
        print("="*70)
    else:
        print("No results")