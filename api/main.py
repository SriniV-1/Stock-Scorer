"""
FastAPI service exposing the stock scoring engine.

Wraps the StockScoringEngine pipeline behind a small REST API and serves the
single-page research frontend. Results are cached in-memory with a TTL so
repeated lookups of the same ticker don't re-hit Yahoo Finance.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.scoring.engine import StockScoringEngine
from src.scoring.final_scorer import FinalScorer
from src.utils.config import METRICS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stockscorer.api")

app = FastAPI(
    title="Stock Scorer API",
    description="Peer-relative fundamental scoring for US equities.",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)

# Heavy objects — build once and reuse across requests.
_engine = StockScoringEngine()
_interpreter = FinalScorer()

# Flatten metric metadata (display name + description) for the response.
_METRIC_META: Dict[str, Dict[str, str]] = {}
for _category, _metrics in METRICS.items():
    for _name, _info in _metrics.items():
        _METRIC_META[_name] = {
            "display_name": _info.get("display_name")
            or _info.get("dsiplay_name")  # tolerate a typo in the config
            or _name.replace("_", " ").title(),
            "description": _info.get("description", ""),
            "lower_is_better": _info.get("lower_is_better", False),
        }

_CACHE_TTL_SECONDS = 60 * 60  # 1 hour
_cache: Dict[str, tuple[float, Dict[str, Any]]] = {}
_cache_lock = Lock()

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


def _serialize(result, cached: bool) -> Dict[str, Any]:
    """Turn a ScoringResult into the JSON payload the frontend consumes."""
    interpretation = _interpreter.interpret_score(result.final_score)
    categories = []
    for name, cat in result.category_scores.items():
        metrics = []
        for m in cat.metric_scores:
            meta = _METRIC_META.get(m.metric_name, {})
            metrics.append(
                {
                    "name": m.metric_name,
                    "display_name": meta.get(
                        "display_name", m.metric_name.replace("_", " ").title()
                    ),
                    "description": meta.get("description", ""),
                    "lower_is_better": meta.get("lower_is_better", False),
                    "raw_value": m.raw_value,
                    "percentile": m.percentile,
                    "score": m.score,
                }
            )
        categories.append(
            {
                "name": name,
                "score": round(cat.score, 1),
                "weight": cat.weight,
                "contribution": round(cat.score * cat.weight, 1),
                "metrics": metrics,
            }
        )
    # Largest weighted contribution first — drives the report ordering.
    categories.sort(key=lambda c: c["contribution"], reverse=True)

    return {
        "ticker": result.ticker,
        "final_score": round(result.final_score, 1),
        "rating": interpretation["rating"],
        "description": interpretation["description"],
        "action": interpretation["action"],
        "summary": result.summary,
        "categories": categories,
        "warnings": result.warnings,
        "peer_count": result.peer_count,
        "timestamp": result.timestamp.isoformat(),
        "cached": cached,
    }


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


@app.get("/api/score/{ticker}")
def score(ticker: str, refresh: bool = False) -> Dict[str, Any]:
    ticker = ticker.strip().upper()
    if not ticker or not ticker.replace(".", "").replace("-", "").isalnum():
        raise HTTPException(status_code=400, detail="Invalid ticker symbol.")

    now = time.time()
    if not refresh:
        with _cache_lock:
            hit = _cache.get(ticker)
            if hit and now - hit[0] < _CACHE_TTL_SECONDS:
                payload = dict(hit[1])
                payload["cached"] = True
                return payload

    logger.info("Scoring %s (refresh=%s)", ticker, refresh)
    result = _engine.score_stock(ticker, force_refresh=refresh)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Could not score '{ticker}'. The symbol may be invalid or "
            "missing the fundamental data required for peer comparison.",
        )

    payload = _serialize(result, cached=False)
    with _cache_lock:
        _cache[ticker] = (now, payload)
    return payload


# Serve the single-page frontend at the root.
if FRONTEND_DIR.exists():

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
