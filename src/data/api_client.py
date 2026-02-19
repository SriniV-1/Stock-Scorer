"""
Fetches financial data from Yahoo Finance with rate limiting and retry logic.

ENHANCEMENTS:
- Better field name fallbacks
- Calculated PEG ratio if missing
- More robust metric extraction
- Diagnostic logging
"""

import yfinance as yf
import pandas as pd
import logging
import time
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from src.utils.models import StockMetrics

logger = logging.getLogger(__name__)


class YahooFinanceClient:
    """
    Wrapper around yfinance with rate limiting and retry logic.
    """
    
    def __init__(self, requests_per_second: float = 2.0):
        """
        Args:
            requests_per_second: Max API calls per second (default: 2)
        """
        self.cache = {}
        self.min_request_interval = 1.0 / requests_per_second
        self.last_request_time = 0
    
    def _wait_for_rate_limit(self):
        """Ensure we don't exceed rate limit"""
        elapsed = time.time() - self.last_request_time
        if elapsed < self.min_request_interval:
            sleep_time = self.min_request_interval - elapsed
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            time.sleep(sleep_time)
        self.last_request_time = time.time()
    
    def _fetch_with_retry(self, ticker: str, max_retries: int = 3):
        """
        Fetch stock data with exponential backoff retry.
        """
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                stock = yf.Ticker(ticker)
                info = stock.info
                
                if info and len(info) > 5:
                    logger.debug(f"Got {len(info)} fields for {ticker}")
                    return stock
                else:
                    logger.warning(f"Insufficient data for {ticker}, attempt {attempt + 1}")
            
            except Exception as e:
                error_msg = str(e)
                
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    wait_time = (2 ** attempt) * 2
                    logger.warning(f"Rate limited on {ticker}, waiting {wait_time}s...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"Error fetching {ticker}: {e}")
                    if attempt < max_retries - 1:
                        time.sleep(1)
                    else:
                        return None
        
        logger.error(f"Failed to fetch {ticker} after {max_retries} attempts")
        return None
    
    def get_stock_metrics(
        self,
        ticker: str,
        use_cache: bool = True
    ) -> Optional[StockMetrics]:
        """
        Fetch current financial metrics for a stock.
        
        ENHANCED: Better field extraction with fallbacks
        """
        ticker = ticker.upper()
        
        # Check cache
        if use_cache and ticker in self.cache:
            cached_data, timestamp = self.cache[ticker]
            if datetime.now() - timestamp < timedelta(days=1):
                logger.info(f"Using cached data for {ticker}")
                return cached_data
        
        # Fetch with retry logic
        stock = self._fetch_with_retry(ticker)
        
        if not stock:
            logger.error(f"Failed to fetch stock object for {ticker}")
            return None
        
        try:
            info = stock.info
            
            if not info:
                logger.error(f"stock.info is empty for {ticker}")
                return None
            
            logger.debug(f"Got info for {ticker} with {len(info)} fields")
            
            # Extract metrics with improved fallbacks
            metrics = StockMetrics(
                ticker=ticker,
                
                # Valuation (with fallbacks)
                pe_ratio=self._get_pe_ratio(info),
                peg_ratio=self._get_peg_ratio(info, stock),
                price_to_fcf=self._calculate_price_to_fcf(stock, info),
                
                # Growth (with calculation fallbacks)
                revenue_growth=self._get_revenue_growth(info, stock),
                eps_growth=self._calculate_eps_growth(stock),
                
                # Profitability (with multiple field names)
                roe=self._get_roe(info),
                operating_margin=self._get_operating_margin(info),
                net_margin=self._get_net_margin(info),
                
                # Risk
                debt_to_equity=self._get_debt_to_equity(info),
                current_ratio=info.get('currentRatio'),
                beta=info.get('beta'),
                
                # Metadata
                industry=info.get('industry'),
                sector=info.get('sector'),
                market_cap=info.get('marketCap'),
                last_updated=datetime.now()
            )
            
            # Cache the result
            self.cache[ticker] = (metrics, datetime.now())
            
            logger.info(f"Successfully created StockMetrics for {ticker}")
            return metrics
        
        except Exception as e:
            logger.error(f"Failed to create StockMetrics for {ticker}: {type(e).__name__}: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None
    
    # ========== ENHANCED EXTRACTION METHODS ==========
    
    def _get_pe_ratio(self, info: Dict) -> Optional[float]:
        """Get P/E ratio with fallbacks"""
        return (
            info.get('trailingPE') or 
            info.get('forwardPE') or 
            info.get('regularMarketPE')
        )
    
    def _get_peg_ratio(self, info: Dict, stock) -> Optional[float]:
        """
        Get PEG ratio with calculation fallback.
        
        If Yahoo doesn't provide it, calculate as: P/E / (EPS Growth % * 100)
        """
        # Try direct field first
        peg = info.get('pegRatio') or info.get('trailingPegRatio')
        
        if peg:
            return peg
        
        # Calculate if we have P/E and growth
        pe = self._get_pe_ratio(info)
        eps_growth = self._calculate_eps_growth(stock)
        
        if pe and eps_growth and eps_growth > 0:
            # PEG = P/E / (growth% * 100)
            # e.g., P/E of 20 with 10% growth = 20 / 10 = 2.0
            peg_calculated = pe / (eps_growth * 100)
            logger.debug(f"Calculated PEG: {peg_calculated:.2f}")
            return peg_calculated
        
        logger.debug("PEG ratio not available")
        return None
    
    def _get_revenue_growth(self, info: Dict, stock) -> Optional[float]:
        """Get revenue growth with calculation fallback"""
        # Try direct field
        growth = info.get('revenueGrowth')
        
        if growth is not None:
            return growth
        
        # Calculate from financials
        try:
            financials = stock.financials
            if financials is not None and not financials.empty:
                if 'Total Revenue' in financials.index:
                    revenue_data = financials.loc['Total Revenue']
                    if len(revenue_data) >= 2:
                        current = revenue_data.iloc[0]
                        previous = revenue_data.iloc[1]
                        if previous != 0:
                            growth = (current - previous) / abs(previous)
                            logger.debug(f"Calculated revenue growth: {growth:.2%}")
                            return growth
        except Exception as e:
            logger.debug(f"Could not calculate revenue growth: {e}")
        
        return None
    
    def _get_roe(self, info: Dict) -> Optional[float]:
        """Get ROE with multiple field name attempts"""
        return (
            info.get('returnOnEquity') or
            info.get('ROE') or
            info.get('roe')
        )
    
    def _get_operating_margin(self, info: Dict) -> Optional[float]:
        """Get operating margin with fallbacks"""
        return (
            info.get('operatingMargins') or
            info.get('operatingMargin') or
            info.get('OperatingMargin')
        )
    
    def _get_net_margin(self, info: Dict) -> Optional[float]:
        """
        Get net margin with multiple field attempts.
        
        Yahoo Finance usually has this as 'profitMargins'
        """
        return (
            info.get('profitMargins') or
            info.get('netProfitMargin') or
            info.get('NetMargin') or
            info.get('profit_margins')
        )
    
    def _get_debt_to_equity(self, info: Dict) -> Optional[float]:
        """Get debt/equity with fallbacks"""
        return (
            info.get('debtToEquity') or
            info.get('Debt_To_Equity') or
            info.get('debt_equity')
        )
    
    def _calculate_price_to_fcf(self, stock, info: Dict) -> Optional[float]:
        """
        Calculate Price to Free Cash Flow with improved field detection.
        """
        try:
            market_cap = info.get('marketCap')
            
            if not market_cap:
                logger.debug("No market cap available")
                return None
            
            # Get cash flow statement
            cash_flow = stock.cashflow
            
            if cash_flow is None or cash_flow.empty:
                logger.debug("No cash flow data available")
                return None
            
            # Try multiple possible field names
            fcf = None
            possible_fields = [
                'Free Cash Flow',
                'FreeCashFlow',
                'Free_Cash_Flow',
                'Operating Cash Flow'  # Fallback
            ]
            
            for field in possible_fields:
                if field in cash_flow.index:
                    fcf = cash_flow.loc[field].iloc[0]
                    logger.debug(f"Found FCF using field: {field}")
                    break
            
            if fcf and fcf > 0:
                return market_cap / fcf
            
            logger.debug(f"Invalid or missing FCF value")
            return None
        
        except Exception as e:
            logger.debug(f"Could not calculate Price/FCF: {e}")
            return None
    
    def _calculate_eps_growth(self, stock) -> Optional[float]:
        """
        Calculate EPS growth with improved field detection.
        """
        try:
            financials = stock.financials
            
            if financials is None or financials.empty:
                logger.debug("No financials data available")
                return None
            
            # Try multiple possible field names
            eps_data = None
            possible_fields = [
                'Basic EPS',
                'BasicEPS',
                'Diluted EPS',
                'DilutedEPS',
                'EPS'
            ]
            
            for field in possible_fields:
                if field in financials.index:
                    eps_data = financials.loc[field]
                    logger.debug(f"Found EPS using field: {field}")
                    break
            
            if eps_data is None:
                logger.debug("No EPS field found in financials")
                return None
            
            if len(eps_data) < 2:
                logger.debug("Not enough EPS history")
                return None
            
            # Calculate growth
            current_eps = eps_data.iloc[0]
            previous_eps = eps_data.iloc[1]
            
            if previous_eps == 0:
                logger.debug("Previous EPS is zero")
                return None
            
            growth = (current_eps - previous_eps) / abs(previous_eps)
            return growth
        
        except Exception as e:
            logger.debug(f"Could not calculate EPS growth: {e}")
            return None
    
    # ========== OTHER METHODS (UNCHANGED) ==========
    
    def get_multiple_stocks(
        self,
        tickers: List[str],
        delay_between: float = 0.5
    ) -> Dict[str, StockMetrics]:
        """Fetch metrics for multiple stocks with delays."""
        results = {}
        
        for i, ticker in enumerate(tickers):
            logger.info(f"Fetching {ticker} ({i+1}/{len(tickers)})...")
            
            metrics = self.get_stock_metrics(ticker)
            
            if metrics:
                results[ticker] = metrics
            else:
                logger.warning(f"Failed to fetch {ticker}")
            
            if i < len(tickers) - 1:
                time.sleep(delay_between)
        
        return results
    
    def get_historical_price_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """Fetch historical price data."""
        try:
            self._wait_for_rate_limit()
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            return hist
        except Exception as e:
            logger.error(f"Failed to fetch historical data for {ticker}: {e}")
            return pd.DataFrame()


# ========== DIAGNOSTIC TOOL ==========

def diagnose_ticker(ticker: str):
    """
    Diagnostic tool to see what fields Yahoo Finance actually returns.
    
    Usage:
        python -m src.data.api_client
    """
    import json
    
    print(f"\n{'='*70}")
    print(f"DIAGNOSING: {ticker}")
    print('='*70)
    
    stock = yf.Ticker(ticker)
    info = stock.info
    
    print(f"\nAvailable fields ({len(info)} total):")
    print("-" * 70)
    
    # Group by category
    valuation_fields = {}
    growth_fields = {}
    profitability_fields = {}
    risk_fields = {}
    other_fields = {}
    
    for key, value in sorted(info.items()):
        key_lower = key.lower()
        
        if any(x in key_lower for x in ['pe', 'peg', 'price', 'valuation', 'fcf']):
            valuation_fields[key] = value
        elif any(x in key_lower for x in ['growth', 'revenue', 'earnings', 'eps']):
            growth_fields[key] = value
        elif any(x in key_lower for x in ['margin', 'roe', 'roa', 'profit']):
            profitability_fields[key] = value
        elif any(x in key_lower for x in ['debt', 'equity', 'ratio', 'beta', 'current']):
            risk_fields[key] = value
        else:
            other_fields[key] = value
    
    def print_fields(category, fields_dict):
        if fields_dict:
            print(f"\n{category}:")
            for k, v in list(fields_dict.items())[:10]:  # Limit to 10
                if v is not None:
                    print(f"  {k}: {v}")
    
    print_fields("VALUATION", valuation_fields)
    print_fields("GROWTH", growth_fields)
    print_fields("PROFITABILITY", profitability_fields)
    print_fields("RISK", risk_fields)
    
    # Try to get financials
    print("\n" + "-" * 70)
    print("FINANCIAL STATEMENTS:")
    print("-" * 70)
    
    financials = stock.financials
    if financials is not None and not financials.empty:
        print(f"\nFinancials available ({len(financials)} rows)")
        print("Sample fields:")
        for field in list(financials.index)[:10]:
            print(f"  - {field}")
    else:
        print("No financials available")
    
    cash_flow = stock.cashflow
    if cash_flow is not None and not cash_flow.empty:
        print(f"\nCash flow available ({len(cash_flow)} rows)")
        print("Sample fields:")
        for field in list(cash_flow.index)[:10]:
            print(f"  - {field}")
    else:
        print("No cash flow available")


# Testing
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run diagnostic
    diagnose_ticker('AAPL')
    
    print("\n\n" + "="*70)
    print("TESTING API CLIENT")
    print("="*70)
    
    client = YahooFinanceClient()
    
    metrics = client.get_stock_metrics('AAPL')
    
    if metrics:
        print(f"\n✅ SUCCESS!")
        print(f"Ticker: {metrics.ticker}")
        print(f"Industry: {metrics.industry}")
        print(f"Sector: {metrics.sector}")
        print(f"\nValuation:")
        print(f"  P/E Ratio: {metrics.pe_ratio}")
        print(f"  PEG Ratio: {metrics.peg_ratio}")
        print(f"  Price/FCF: {metrics.price_to_fcf}")
        print(f"\nGrowth:")
        print(f"  Revenue Growth: {metrics.revenue_growth:.2%}" if metrics.revenue_growth else "  Revenue Growth: N/A")
        print(f"  EPS Growth: {metrics.eps_growth:.2%}" if metrics.eps_growth else "  EPS Growth: N/A")
        print(f"\nProfitability:")
        print(f"  ROE: {metrics.roe:.2%}" if metrics.roe else "  ROE: N/A")
        print(f"  Operating Margin: {metrics.operating_margin:.2%}" if metrics.operating_margin else "  Operating Margin: N/A")
        print(f"  Net Margin: {metrics.net_margin:.2%}" if metrics.net_margin else "  Net Margin: N/A")
        print(f"\nRisk:")
        print(f"  Debt/Equity: {metrics.debt_to_equity}")
        print(f"  Current Ratio: {metrics.current_ratio}")
        print(f"  Beta: {metrics.beta}")
        
        print("\n" + "="*70)
        print("✅ API CLIENT WORKING!")
        print("="*70)