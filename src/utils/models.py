"""
Data models using Pydantic for validation.

Why Pydantic? It ensures data has correct types and catches errors early.
Example: If we expect a float but get a string, Pydantic raises an error.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, List
from datetime import datetime


class StockMetrics(BaseModel):
    """
    Represents all financial metrics for a single stock.
    
    Optional fields allow for missing data (some stocks don't report all metrics).
    """
    ticker: str = Field(..., description="Stock ticker symbol")
    
    # Valuation metrics
    pe_ratio: Optional[float] = Field(None, ge=0, description="Price-to-Earnings")
    peg_ratio: Optional[float] = Field(None, description="PEG Ratio")
    price_to_fcf: Optional[float] = Field(None, ge=0, description="Price to FCF")
    
    # Growth metrics
    revenue_growth: Optional[float] = Field(None, description="Revenue growth rate")
    eps_growth: Optional[float] = Field(None, description="EPS growth rate")
    
    # Profitability metrics
    roe: Optional[float] = Field(None, description="Return on Equity")
    operating_margin: Optional[float] = Field(None, description="Operating margin")
    net_margin: Optional[float] = Field(None, description="Net profit margin")
    
    # Risk metrics
    debt_to_equity: Optional[float] = Field(None, ge=0, description="Debt/Equity")
    current_ratio: Optional[float] = Field(None, ge=0, description="Current ratio")
    beta: Optional[float] = Field(None, description="Beta coefficient")
    
    # Metadata
    industry: Optional[str] = None
    sector: Optional[str] = None
    market_cap: Optional[float] = None
    last_updated: datetime = Field(default_factory=datetime.now)
    
    @validator('pe_ratio', 'peg_ratio', 'price_to_fcf')
    def validate_positive_valuation(cls, v):
        """Ensure valuation metrics are positive if provided"""
        if v is not None and v < 0:
            raise ValueError("Valuation metrics cannot be negative")
        return v
    
    class Config:
        arbitrary_types_allowed = True


class MetricScore(BaseModel):
    """Score for a single metric"""
    metric_name: str
    raw_value: Optional[float]
    percentile: Optional[float] = Field(None, ge=0, le=100)
    score: Optional[float] = Field(None, ge=0, le=100)
    peer_median: Optional[float] = None


class CategoryScore(BaseModel):
    """Score for a category (e.g., Valuation)"""
    category: str
    score: float = Field(..., ge=0, le=100)
    weight: float = Field(..., ge=0, le=1)
    metric_scores: List[MetricScore]


class ScoringResult(BaseModel):
    """Complete scoring output"""
    ticker: str
    final_score: float = Field(..., ge=0, le=100)
    category_scores: Dict[str, CategoryScore]
    
    # Explanation
    strengths: List[str] = []
    weaknesses: List[str] = []
    warnings: List[str] = []
    summary: str = ""
    
    # Metadata
    peer_count: int
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        arbitrary_types_allowed = True
