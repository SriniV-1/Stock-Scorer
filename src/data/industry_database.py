"""
Industry-based peer groupings with intelligent fallbacks.

This enables the system to score ANY stock, not just hardcoded ones.
"""

import yfinance as yf
import logging

logger = logging.getLogger(__name__)

# Major stocks by industry (comprehensive coverage)
INDUSTRY_STOCKS = {
    # Technology
    'Internet Content & Information': [
        'GOOGL', 'META', 'SNAP', 'PINS', 'RBLX', 'NFLX'
    ],
    'Software—Application': [
        'MSFT', 'ADBE', 'CRM', 'ORCL', 'INTU', 'SNOW', 'WDAY', 'NOW'
    ],
    'Software—Infrastructure': [
        'MSFT', 'ORCL', 'SAP', 'NOW', 'TEAM', 'ZS', 'DDOG'
    ],
    'Semiconductors': [
        'NVDA', 'AMD', 'INTC', 'TSM', 'QCOM', 'AVGO', 'MU', 'AMAT'
    ],
    'Consumer Electronics': [
        'AAPL', 'SONY', 'DELL', 'HPQ', 'LOGI'
    ],
    'Electronic Gaming & Multimedia': [
        'RBLX', 'EA', 'TTWO', 'ATVI', 'U', 'NFLX'
    ],
    
    # E-commerce & Retail
    'Internet Retail': [
        'AMZN', 'EBAY', 'ETSY', 'W', 'CHWY', 'SHOP'
    ],
    'Specialty Retail': [
        'HD', 'LOW', 'TJX', 'ROST', 'BBWI', 'ULTA'
    ],
    'Discount Stores': [
        'WMT', 'TGT', 'COST', 'DG', 'DLTR'
    ],
    
    # Financial Services
    'Banks—Diversified': [
        'JPM', 'BAC', 'WFC', 'C', 'USB', 'PNC', 'TFC'
    ],
    'Banks—Regional': [
        'KEY', 'RF', 'FITB', 'HBAN', 'CFG', 'ZION'
    ],
    'Capital Markets': [
        'GS', 'MS', 'SCHW', 'IBKR', 'SF', 'BLK', 'SPGI'
    ],
    'Insurance—Life': [
        'PRU', 'MET', 'AFL', 'LNC', 'PFG'
    ],
    'Insurance—Property & Casualty': [
        'BRK-B', 'PGR', 'ALL', 'TRV', 'AIG', 'CB'
    ],
    'Credit Services': [
        'V', 'MA', 'AXP', 'DFS', 'COF'
    ],
    
    # Energy
    'Oil & Gas Integrated': [
        'XOM', 'CVX', 'COP', 'BP', 'SHEL', 'TTE'
    ],
    'Oil & Gas E&P': [
        'EOG', 'PXD', 'DVN', 'FANG', 'MRO', 'OXY'
    ],
    'Oil & Gas Midstream': [
        'EPD', 'ET', 'WMB', 'KMI', 'OKE', 'MPLX'
    ],
    'Oil & Gas Refining & Marketing': [
        'MPC', 'PSX', 'VLO', 'HFC'
    ],
    
    # Healthcare
    'Drug Manufacturers—General': [
        'JNJ', 'PFE', 'ABBV', 'MRK', 'LLY', 'BMY', 'NVO'
    ],
    'Biotechnology': [
        'AMGN', 'GILD', 'BIIB', 'REGN', 'VRTX', 'MRNA', 'ALNY'
    ],
    'Medical Devices': [
        'ABT', 'TMO', 'DHR', 'SYK', 'BSX', 'MDT', 'ISRG'
    ],
    'Health Care Plans': [
        'UNH', 'CVS', 'CI', 'HUM', 'ELV', 'CNC'
    ],
    'Medical Instruments & Supplies': [
        'ABT', 'SYK', 'BSX', 'BDX', 'BAX', 'ZBH'
    ],
    
    # Consumer
    'Beverages—Non-Alcoholic': [
        'KO', 'PEP', 'MNST', 'CELH', 'KDP'
    ],
    'Packaged Foods': [
        'GIS', 'KHC', 'K', 'CPB', 'MKC', 'HSY'
    ],
    'Restaurants': [
        'MCD', 'SBUX', 'CMG', 'YUM', 'QSR', 'WEN', 'DPZ'
    ],
    'Auto Manufacturers': [
        'TSLA', 'F', 'GM', 'RIVN', 'LCID', 'TM'
    ],
    'Apparel Manufacturing': [
        'NKE', 'LULU', 'VFC', 'UAA', 'CROX'
    ],
    
    # Utilities
    'Utilities—Regulated Electric': [
        'NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'XEL'
    ],
    'Utilities—Diversified': [
        'NEE', 'DUK', 'SO', 'AEP', 'XEL', 'WEC'
    ],
    
    # Telecom
    'Telecom Services': [
        'T', 'VZ', 'TMUS', 'CHTR', 'CMCSA'
    ],
    
    # Real Estate
    'REIT—Residential': [
        'EQR', 'AVB', 'ESS', 'MAA', 'UDR', 'CPT'
    ],
    'REIT—Retail': [
        'SPG', 'REG', 'KIM', 'BRX', 'ROIC', 'FRT'
    ],
    'REIT—Office': [
        'BXP', 'VNO', 'SLG', 'ARE', 'DEI'
    ],
    'REIT—Industrial': [
        'PLD', 'DRE', 'FR', 'STAG', 'TRNO'
    ],
    'REIT—Healthcare Facilities': [
        'WELL', 'VTR', 'PEAK', 'DOC', 'HR'
    ],
    
    # Industrial
    'Aerospace & Defense': [
        'LMT', 'RTX', 'BA', 'NOC', 'GD', 'LHX', 'TXT'
    ],
    'Railroads': [
        'UNP', 'CSX', 'NSC', 'CP', 'CNI'
    ],
    'Airlines': [
        'AAL', 'DAL', 'UAL', 'LUV', 'ALK', 'JBLU'
    ],
    'Industrial Distribution': [
        'GWW', 'FAST', 'WCC', 'DCI'
    ],
    
    # Materials
    'Chemicals': [
        'LIN', 'APD', 'ECL', 'DD', 'DOW', 'PPG'
    ],
    'Steel': [
        'NUE', 'STLD', 'CLF', 'X', 'MT'
    ],
    'Copper': [
        'FCX', 'SCCO', 'TECK'
    ],
    'Gold': [
        'NEM', 'GOLD', 'AEM', 'FNV', 'WPM'
    ],
}

# Sector-level fallback (if industry not found)
SECTOR_STOCKS = {
    'Technology': [
        'AAPL', 'MSFT', 'GOOGL', 'META', 'NVDA', 'AMZN', 'TSLA',
        'ADBE', 'CRM', 'ORCL', 'INTC', 'AMD', 'QCOM', 'AVGO',
        'NOW', 'INTU', 'AMAT', 'LRCX', 'KLAC', 'SNPS'
    ],
    'Financial Services': [
        'JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW',
        'USB', 'PNC', 'AXP', 'SPGI', 'V', 'MA', 'COF'
    ],
    'Healthcare': [
        'UNH', 'JNJ', 'LLY', 'ABBV', 'MRK', 'TMO', 'ABT', 'PFE',
        'DHR', 'AMGN', 'CVS', 'CI', 'HUM', 'ISRG', 'VRTX'
    ],
    'Energy': [
        'XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX', 'VLO',
        'OXY', 'DVN', 'FANG', 'PXD', 'KMI', 'WMB'
    ],
    'Consumer Cyclical': [
        'AMZN', 'TSLA', 'HD', 'MCD', 'NKE', 'SBUX', 'LOW', 'TJX',
        'CMG', 'BKNG', 'GM', 'F', 'MAR', 'ABNB'
    ],
    'Consumer Defensive': [
        'WMT', 'PG', 'KO', 'PEP', 'COST', 'PM', 'MO', 'CL',
        'KHC', 'GIS', 'KMB', 'CLX', 'EL', 'MDLZ'
    ],
    'Utilities': [
        'NEE', 'DUK', 'SO', 'D', 'AEP', 'EXC', 'SRE', 'XEL',
        'WEC', 'ES', 'ED', 'FE', 'AWK', 'PEG'
    ],
    'Real Estate': [
        'PLD', 'AMT', 'CCI', 'EQIX', 'PSA', 'SPG', 'O', 'WELL',
        'DLR', 'AVB', 'EQR', 'VTR', 'ARE', 'SBAC'
    ],
    'Communication Services': [
        'GOOGL', 'META', 'NFLX', 'DIS', 'CMCSA', 'T', 'VZ', 'TMUS',
        'CHTR', 'DISH', 'PARA', 'WBD', 'EA', 'TTWO'
    ],
    'Industrials': [
        'UPS', 'UNP', 'HON', 'RTX', 'BA', 'CAT', 'DE', 'LMT',
        'GE', 'MMM', 'EMR', 'GD', 'CSX', 'NSC', 'FDX'
    ],
    'Basic Materials': [
        'LIN', 'SHW', 'APD', 'FCX', 'NEM', 'ECL', 'DD', 'NUE',
        'DOW', 'PPG', 'VMC', 'MLM', 'CTVA', 'ALB'
    ]
}


def get_peers_for_any_stock(ticker: str, limit: int = 10) -> list:
    """
    Get peers for ANY stock using multiple fallback strategies.
    
    Strategy:
    1. Try industry-specific peers (most precise)
    2. Fall back to sector peers (broader)
    3. Last resort: return stock alone
    
    Args:
        ticker: Stock ticker symbol
        limit: Number of peers to return
    
    Returns:
        List of peer ticker symbols (includes the stock itself)
    """
    try:
        # Import here to avoid circular dependency
        from src.data.api_client import YahooFinanceClient
        
        client = YahooFinanceClient(requests_per_second=2.0)
        
        # Fetch stock info
        metrics = client.get_stock_metrics(ticker)
        
        if not metrics:
            logger.warning(f"Could not fetch data for {ticker}")
            return [ticker]
        
        industry = metrics.industry
        sector = metrics.sector
        
        logger.info(f"{ticker} - Industry: {industry}, Sector: {sector}")
        
        # Strategy 1: Industry-specific peers
        if industry and industry in INDUSTRY_STOCKS:
            peers = list(INDUSTRY_STOCKS[industry][:limit])
            logger.info(f"Found {len(peers)} industry peers for {ticker}")
            if ticker not in peers:
                peers = [ticker] + peers
            return list(set(peers))[:limit]
        
        # Strategy 2: Sector-level peers
        if sector and sector in SECTOR_STOCKS:
            peers = list(SECTOR_STOCKS[sector][:limit])
            logger.info(f"Using sector peers for {ticker}")
            if ticker not in peers:
                peers = [ticker] + peers
            return list(set(peers))[:limit]
        
        # Fallback
        logger.warning(f"No peers found for {ticker}, using as standalone")
        return [ticker]
    
    except Exception as e:
        logger.error(f"Error getting peers for {ticker}: {e}")
        return [ticker]


def get_sp500_tickers() -> list:
    """
    Get list of major S&P 500 tickers for scanning.
    
    This is a curated list of the top ~100 most liquid stocks.
    """
    return [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'BRK-B', 'LLY', 'V',
        'UNH', 'XOM', 'JPM', 'JNJ', 'WMT', 'MA', 'PG', 'AVGO', 'HD', 'CVX',
        'MRK', 'ABBV', 'COST', 'KO', 'ADBE', 'PEP', 'MCD', 'CSCO', 'TMO', 'ACN',
        'CRM', 'NFLX', 'ABT', 'LIN', 'ORCL', 'NKE', 'DHR', 'WFC', 'AMD', 'DIS',
        'TXN', 'PM', 'VZ', 'CMCSA', 'INTC', 'NEE', 'INTU', 'UPS', 'RTX', 'QCOM',
        'AMGN', 'PFE', 'SPGI', 'COP', 'HON', 'IBM', 'GE', 'LOW', 'CAT', 'AMAT',
        'UNP', 'BA', 'BLK', 'ELV', 'SYK', 'AXP', 'DE', 'SBUX', 'BKNG', 'GILD',
        'ADI', 'LMT', 'MDT', 'PLD', 'TJX', 'VRTX', 'ADP', 'SCHW', 'MDLZ', 'CI',
        'MMC', 'REGN', 'CB', 'CVS', 'AMT', 'ISRG', 'SO', 'ZTS', 'MO', 'BDX',
        'DUK', 'ETN', 'SLB', 'PGR', 'CME', 'BSX', 'C', 'GS', 'EOG', 'ITW'
    ]


def get_nasdaq100_tickers() -> list:
    """Get major NASDAQ 100 tickers"""
    return [
        'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'META', 'TSLA', 'AVGO', 'COST', 'NFLX',
        'ADBE', 'PEP', 'CSCO', 'TMUS', 'CMCSA', 'AMD', 'INTC', 'TXN', 'QCOM', 'INTU',
        'AMGN', 'AMAT', 'HON', 'SBUX', 'BKNG', 'ADI', 'GILD', 'VRTX', 'MDLZ', 'ADP',
        'REGN', 'ISRG', 'LRCX', 'PANW', 'CSX', 'SNPS', 'CDNS', 'KLAC', 'MELI', 'NXPI',
        'MAR', 'ABNB', 'ORLY', 'MNST', 'ASML', 'CTAS', 'CRWD', 'FTNT', 'MRVL', 'WDAY'
    ]

