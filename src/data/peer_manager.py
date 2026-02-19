"""
Manages peer group data with AUTOMATIC industry detection.

Key feature: Works for ANY stock by auto-detecting peers.
"""

import sqlite3
import json
import pandas as pd
from typing import List, Dict, Optional
from pathlib import Path
import logging
from datetime import datetime

from src.data.api_client import YahooFinanceClient
from src.data.industry_database import get_peers_for_any_stock
from src.utils.models import StockMetrics

logger = logging.getLogger(__name__)


class PeerDataManager:
    """
    Manages peer group data with SQLite caching.
    
    NEW: Auto-detects peers by industry/sector for ANY stock.
    """
    
    def __init__(self, db_path: str = "data/peers.db"):
        """
        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.client = YahooFinanceClient()
        
        # Ensure data directory exists
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize database
        self._init_database()
    
    def _init_database(self):
        """Create tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Table for stock metrics
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stock_metrics (
                ticker TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                last_updated TIMESTAMP NOT NULL
            )
        """)
        
        # Table for peer relationships
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS peer_groups (
                ticker TEXT PRIMARY KEY,
                peers TEXT NOT NULL,
                last_updated TIMESTAMP NOT NULL
            )
        """)
        
        conn.commit()
        conn.close()
        
        logger.info(f"Database initialized at {self.db_path}")
    
    def get_peers(self, ticker: str) -> List[str]:
        """
        Get peer tickers for a stock using AUTO-DETECTION.
        
        This is the key enhancement - works for ANY stock!
        
        Args:
            ticker: Stock ticker
        
        Returns:
            List of peer tickers (includes the stock itself)
        """
        ticker = ticker.upper()
        
        # Use universal peer detection
        peers = get_peers_for_any_stock(ticker, limit=10)
        
        # Cache the peer group
        self._cache_peer_group(ticker, peers)
        
        return peers
    
    def _cache_peer_group(self, ticker: str, peers: List[str]):
        """Cache peer group to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO peer_groups (ticker, peers, last_updated)
            VALUES (?, ?, ?)
        """, (ticker, json.dumps(peers), datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
    
    def get_peer_metrics(
        self,
        ticker: str,
        force_refresh: bool = False
    ) -> Dict[str, StockMetrics]:
        """
        Get metrics for a stock and all its peers.
        
        Args:
            ticker: Stock ticker
            force_refresh: If True, ignore cache and fetch fresh data
        
        Returns:
            Dict mapping ticker -> StockMetrics
        """
        peers = self.get_peers(ticker)
        logger.info(f"Fetching data for {ticker} and {len(peers)-1} peers")
        
        results = {}
        
        for peer_ticker in peers:
            # Check cache first (unless force refresh)
            if not force_refresh:
                cached = self._get_cached_metrics(peer_ticker)
                if cached:
                    results[peer_ticker] = cached
                    continue
            
            # Fetch from API
            metrics = self.client.get_stock_metrics(peer_ticker)
            
            if metrics:
                results[peer_ticker] = metrics
                # Cache it
                self._cache_metrics(peer_ticker, metrics)
            else:
                logger.warning(f"Failed to fetch {peer_ticker}")
        
        return results
    
    def _get_cached_metrics(
        self,
        ticker: str,
        max_age_hours: int = 24
    ) -> Optional[StockMetrics]:
        """
        Retrieve cached metrics if fresh enough.
        
        Args:
            ticker: Stock ticker
            max_age_hours: Maximum age of cache in hours
        
        Returns:
            StockMetrics or None
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT data, last_updated FROM stock_metrics WHERE ticker = ?",
            (ticker,)
        )
        
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return None
        
        data_json, last_updated = result
        
        # Check age
        last_updated = datetime.fromisoformat(last_updated)
        age_hours = (datetime.now() - last_updated).total_seconds() / 3600
        
        if age_hours > max_age_hours:
            logger.debug(f"Cache for {ticker} is stale ({age_hours:.1f}h old)")
            return None
        
        # Deserialize
        data_dict = json.loads(data_json)
        metrics = StockMetrics(**data_dict)
        
        logger.debug(f"Using cached data for {ticker}")
        return metrics
    
    def _cache_metrics(self, ticker: str, metrics: StockMetrics):
        """Save metrics to cache"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Serialize to JSON
        data_json = metrics.model_dump_json()
        
        cursor.execute("""
            INSERT OR REPLACE INTO stock_metrics (ticker, data, last_updated)
            VALUES (?, ?, ?)
        """, (ticker, data_json, datetime.now().isoformat()))
        
        conn.commit()
        conn.close()
        
        logger.debug(f"Cached data for {ticker}")
    
    def export_peer_data_to_csv(self, ticker: str, output_path: str):
        """
        Export peer data to CSV for analysis.
        
        Args:
            ticker: Stock ticker
            output_path: Where to save CSV
        """
        peer_data = self.get_peer_metrics(ticker)
        
        # Convert to DataFrame
        rows = []
        for t, metrics in peer_data.items():
            row = {
                'ticker': t,
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
                'industry': metrics.industry,
                'sector': metrics.sector
            }
            rows.append(row)
        
        df = pd.DataFrame(rows)
        df.to_csv(output_path, index=False)
        
        logger.info(f"Exported peer data to {output_path}")
        return df


# Testing
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    manager = PeerDataManager()
    
    # Test with NVDA (semiconductors)
    print("\n" + "="*50)
    print("Testing Peer Manager with NVDA")
    print("="*50)
    
    print("\nFinding peers...")
    peers = manager.get_peers('NVDA')
    print(f"Peers: {peers}")
    
    print("\nFetching peer metrics...")
    peer_data = manager.get_peer_metrics('NVDA')
    
    print(f"\n✅ Fetched data for {len(peer_data)} stocks:")
    for ticker, metrics in peer_data.items():
        print(f"  {ticker}: {metrics.industry}")
    
    # Export to CSV
    print("\nExporting to CSV...")
    df = manager.export_peer_data_to_csv('NVDA', 'data/nvda_peers.csv')
    
    print("\n" + "="*50)
    print("✅ PEER MANAGER WORKING!")
    print("="*50)