"""
Fetches financial data from Yahoo Finance with rate limiting and retry logic.
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
        
        Args:
            ticker: Stock symbol
            max_retries: Maximum retry attempts
        
        Returns:
            yfinance.Ticker object or None
        """
        for attempt in range(max_retries):
            try:
                self._wait_for_rate_limit()
                stock = yf.Ticker(ticker)
                info = stock.info  # Trigger the API call
                
                # Check if we got valid data (check for substantial data)
                if info and len(info) > 5:
                    logger.debug(f"Got {len(info)} fields for {ticker}")
                    return stock
                else:
                    logger.warning(f"Insufficient data for {ticker} (got {len(info) if info else 0} fields), attempt {attempt + 1}")
            
            except Exception as e:
                error_msg = str(e)
                
                if "429" in error_msg or "Too Many Requests" in error_msg:
                    # Exponential backoff
                    wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
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
        
        Args:
            ticker: Stock ticker symbol
            use_cache: Whether to use cached data
        
        Returns:
            StockMetrics object or None if fetch fails
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
            logger.debug(f"  Industry: {info.get('industry')}")
            logger.debug(f"  Sector: {info.get('sector')}")
            logger.debug(f"  P/E: {info.get('trailingPE')}")
            
            # Extract metrics
            metrics = StockMetrics(
                ticker=ticker,
                
                # Valuation
                pe_ratio=info.get('trailingPE') or info.get('forwardPE'),
                peg_ratio=info.get('pegRatio'),
                price_to_fcf=self._calculate_price_to_fcf(stock, info),
                
                # Growth
                revenue_growth=info.get('revenueGrowth'),
                eps_growth=self._calculate_eps_growth(stock),
                
                # Profitability
                roe=info.get('returnOnEquity'),
                operating_margin=info.get('operatingMargins'),
                net_margin=info.get('profitMargins'),
                
                # Risk
                debt_to_equity=info.get('debtToEquity'),
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
    
    def _calculate_price_to_fcf(self, stock, info: Dict) -> Optional[float]:
        """
        Calculate Price to Free Cash Flow.
        
        Formula: Market Cap / Free Cash Flow
        """
        try:
            market_cap = info.get('marketCap')
            
            if not market_cap:
                logger.debug("No market cap available")
                return None
            
            # Try to get FCF from cash flow statement
            cash_flow = stock.cashflow
            
            if cash_flow is None or cash_flow.empty:
                logger.debug("No cash flow data available")
                return None
            
            # Try different possible field names
            fcf = None
            if 'Free Cash Flow' in cash_flow.index:
                fcf = cash_flow.loc['Free Cash Flow'].iloc[0]
            elif 'FreeCashFlow' in cash_flow.index:
                fcf = cash_flow.loc['FreeCashFlow'].iloc[0]
            else:
                logger.debug("Free Cash Flow field not found in cash flow statement")
                return None
            
            if fcf and fcf > 0:
                return market_cap / fcf
            
            logger.debug(f"Invalid FCF value: {fcf}")
            return None
        
        except Exception as e:
            logger.debug(f"Could not calculate Price/FCF: {e}")
            return None
    
    def _calculate_eps_growth(self, stock) -> Optional[float]:
        """
        Calculate EPS growth rate (YoY).
        
        Uses trailing EPS from financials.
        """
        try:
            financials = stock.financials
            
            if financials is None or financials.empty:
                logger.debug("No financials data available")
                return None
            
            if 'Basic EPS' not in financials.index:
                logger.debug("'Basic EPS' not in financials index")
                return None
            
            eps_data = financials.loc['Basic EPS']
            
            if len(eps_data) < 2:
                logger.debug("Not enough EPS history (need at least 2 years)")
                return None
            
            # Most recent two years
            current_eps = eps_data.iloc[0]
            previous_eps = eps_data.iloc[1]
            
            if previous_eps == 0:
                logger.debug("Previous EPS is zero, cannot calculate growth")
                return None
            
            growth = (current_eps - previous_eps) / abs(previous_eps)
            return growth
        
        except Exception as e:
            logger.debug(f"Could not calculate EPS growth: {e}")
            return None
    
    def get_multiple_stocks(
        self,
        tickers: List[str],
        delay_between: float = 0.5
    ) -> Dict[str, StockMetrics]:
        """
        Fetch metrics for multiple stocks with delays.
        
        Args:
            tickers: List of ticker symbols
            delay_between: Extra delay between stocks (seconds)
        
        Returns:
            Dict mapping ticker -> StockMetrics
        """
        results = {}
        
        for i, ticker in enumerate(tickers):
            logger.info(f"Fetching {ticker} ({i+1}/{len(tickers)})...")
            
            metrics = self.get_stock_metrics(ticker)
            
            if metrics:
                results[ticker] = metrics
            else:
                logger.warning(f"Failed to fetch {ticker}")
            
            # Extra delay between stocks
            if i < len(tickers) - 1:
                time.sleep(delay_between)
        
        return results
    
    def get_historical_price_data(
        self,
        ticker: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        Fetch historical price data (for backtesting).
        
        Args:
            ticker: Stock symbol
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with OHLCV data
        """
        try:
            self._wait_for_rate_limit()
            stock = yf.Ticker(ticker)
            hist = stock.history(start=start_date, end=end_date)
            return hist
        except Exception as e:
            logger.error(f"Failed to fetch historical data for {ticker}: {e}")
            return pd.DataFrame()


# Testing
if __name__ == "__main__":
    # Set up detailed logging
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    client = YahooFinanceClient()
    
    # Test fetching Apple
    print("\nFetching AAPL data...")
    print("-" * 50)
    
    try:
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
            if metrics.revenue_growth:
                print(f"  Revenue Growth: {metrics.revenue_growth:.2%}")
            else:
                print(f"  Revenue Growth: N/A")
            if metrics.eps_growth:
                print(f"  EPS Growth: {metrics.eps_growth:.2%}")
            else:
                print(f"  EPS Growth: N/A")
            print(f"\nProfitability:")
            if metrics.roe:
                print(f"  ROE: {metrics.roe:.2%}")
            else:
                print(f"  ROE: N/A")
            if metrics.operating_margin:
                print(f"  Operating Margin: {metrics.operating_margin:.2%}")
            else:
                print(f"  Operating Margin: N/A")
            if metrics.net_margin:
                print(f"  Net Margin: {metrics.net_margin:.2%}")
            else:
                print(f"  Net Margin: N/A")
            print(f"\nRisk:")
            print(f"  Debt/Equity: {metrics.debt_to_equity}")
            print(f"  Current Ratio: {metrics.current_ratio}")
            print(f"  Beta: {metrics.beta}")
            
            print("\n" + "="*50)
            print("✅ API CLIENT WORKING CORRECTLY!")
            print("="*50)
        else:
            print("\n❌ Failed to fetch data - metrics is None")
    
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    
    # Test multiple stocks
    print("\n\nTesting multiple stocks...")
    print("-" * 50)
    
    test_tickers = ['MSFT', 'GOOGL']
    results = client.get_multiple_stocks(test_tickers)
    
    print(f"\nSuccessfully fetched {len(results)}/{len(test_tickers)} stocks:")
    for ticker, metrics in results.items():
        print(f"  ✅ {ticker}: {metrics.industry}")