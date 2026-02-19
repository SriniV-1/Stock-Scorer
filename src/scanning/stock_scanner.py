"""
Stock scanner to find top-scoring stocks.

Scans a universe of stocks and ranks them by investment score.
"""

import pandas as pd
import logging
import math
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

from src.scoring.engine import StockScoringEngine
from src.data.industry_database import get_sp500_tickers, get_nasdaq100_tickers

logger = logging.getLogger(__name__)


class StockScanner:
    """
    Scans multiple stocks and ranks by investment score.
    
    Usage:
        scanner = StockScanner()
        top_stocks = scanner.scan_top_stocks(limit=10)
    """
    
    def __init__(self):
        self.engine = StockScoringEngine()

    # -------------------------
    # Utility: safe numeric
    # -------------------------
    @staticmethod
    def _safe_number(value, default=0.0):
        """
        Replace None or NaN with a safe default value.
        Prevents Pydantic validation crashes.
        """
        if value is None:
            return default
        if isinstance(value, float) and math.isnan(value):
            return default
        return value
    
    def scan_stock_universe(
        self,
        tickers: List[str],
        max_workers: int = 10
    ) -> pd.DataFrame:
        """
        Score multiple stocks in parallel.
        
        Args:
            tickers: List of stock symbols to scan
            max_workers: Number of parallel workers (don't set too high!)
        
        Returns:
            DataFrame with scores and key metrics
        """
        results = []
        
        logger.info(f"Scanning {len(tickers)} stocks...")
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_ticker = {
                executor.submit(self._score_single_stock, ticker): ticker 
                for ticker in tickers
            }
            
            for future in tqdm(
                as_completed(future_to_ticker),
                total=len(tickers),
                desc="Scoring stocks"
            ):
                ticker = future_to_ticker[future]
                
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                except Exception as e:
                    logger.error(f"Error scoring {ticker}: {e}")
        
        if not results:
            return pd.DataFrame()
        
        df = pd.DataFrame(results)
        df = df.sort_values('final_score', ascending=False).reset_index(drop=True)
        
        return df
    
    def _score_single_stock(self, ticker: str) -> Dict:
        """
        Score a single stock and extract key info.
        
        Returns dict with score and metrics, or None if failed.
        """
        try:
            result = self.engine.score_stock(ticker)
            
            if not result:
                return None
            
            return {
                'ticker': ticker,
                'final_score': self._safe_number(result.final_score),

                'valuation_score': self._safe_number(
                    result.category_scores['valuation'].score
                ),
                'growth_score': self._safe_number(
                    result.category_scores['growth'].score
                ),
                'profitability_score': self._safe_number(
                    result.category_scores['profitability'].score
                ),
                'risk_score': self._safe_number(
                    result.category_scores['risk'].score
                ),

                'summary': result.summary,
                'top_strength': result.strengths[0] if result.strengths else '',
                'top_weakness': result.weaknesses[0] if result.weaknesses else '',
                'peer_count': result.peer_count,
            }
        
        except Exception as e:
            logger.error(f"Failed to score {ticker}: {e}")
            return None
    
    def scan_top_stocks(
        self,
        universe: str = 'sp500',
        limit: int = 10,
        min_score: float = 60.0
    ) -> pd.DataFrame:
        """
        Find top-scoring stocks from a universe.
        """
        if universe == 'sp500':
            tickers = get_sp500_tickers()
        elif universe == 'nasdaq100':
            tickers = get_nasdaq100_tickers()
        else:
            tickers = get_sp500_tickers()
        
        all_results = self.scan_stock_universe(tickers)
        
        if all_results.empty:
            return pd.DataFrame()
        
        filtered = all_results[all_results['final_score'] >= min_score]
        return filtered.head(limit)
    
    def scan_by_category(
        self,
        category: str,
        limit: int = 10
    ) -> pd.DataFrame:
        """
        Find top stocks by specific category.
        """
        tickers = get_sp500_tickers()
        
        all_results = self.scan_stock_universe(tickers)
        
        if all_results.empty:
            return pd.DataFrame()
        
        score_col = f'{category}_score'
        
        if score_col not in all_results.columns:
            logger.error(f"Invalid category: {category}")
            return pd.DataFrame()
        
        sorted_df = all_results.sort_values(score_col, ascending=False)
        return sorted_df.head(limit)


# -------------------------
# Testing
# -------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    scanner = StockScanner()
    
    print("\n" + "="*70)
    print("STOCK SCANNER TEST")
    print("="*70)
    
    print("\nScanning full S&P 500...\n")

    results = scanner.scan_top_stocks(
        universe='sp500',
        limit=20,
        min_score=0
    )
    
    if not results.empty:
        print("\n" + "-"*70)
        print("TOP STOCKS:")
        print("-"*70)
        
        for idx, row in results.iterrows():
            print(f"\n{idx+1}. {row['ticker']} - {row['final_score']:.1f}/100")
            print(f"   Val: {row['valuation_score']:.0f} | "
                  f"Growth: {row['growth_score']:.0f} | "
                  f"Profit: {row['profitability_score']:.0f} | "
                  f"Risk: {row['risk_score']:.0f}")
        
        print("\n" + "="*70)
        print("✅ STOCK SCANNER WORKING!")
        print("="*70)
    else:
        print("No results")
