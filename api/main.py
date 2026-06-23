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
from threading import Lock, Thread
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

# Company display names, looked up lazily from Yahoo and memoized.
_name_cache: Dict[str, Optional[str]] = {}


def _company_name(ticker: str) -> Optional[str]:
    if ticker in _name_cache:
        return _name_cache[ticker]
    name: Optional[str] = None
    try:
        import yfinance as yf

        info = yf.Ticker(ticker).info
        name = info.get("longName") or info.get("shortName")
    except Exception as e:  # name is best-effort; never block scoring
        logger.info("name lookup failed for %s: %s", ticker, e)
    _name_cache[ticker] = name
    return name

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


@app.get("/api/leaderboard")
def leaderboard(n: int = 5) -> Dict[str, Any]:
    """Top-N highest scores among the tickers analyzed so far.

    Note: scores are peer-relative, so this ranks the stocks that have actually
    been scored (seeded + user lookups) — it is not a market-wide ranking.
    """
    with _cache_lock:
        rows = [p for _, p in _cache.values()]
    total = len(rows)
    rows.sort(key=lambda p: p["final_score"], reverse=True)
    top = [
        {
            "ticker": p["ticker"],
            "name": p.get("name"),
            "final_score": p["final_score"],
            "rating": p["rating"],
        }
        for p in rows[: max(1, n)]
    ]
    return {"top": top, "total": total}


# Warm the leaderboard in the background so the bar is drawn from a real,
# diverse set of large caps rather than a handful of names.
_SEED_TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO",
    "JPM", "BAC", "V", "MA", "WMT", "COST", "KO", "PEP",
    "JNJ", "UNH", "LLY", "XOM", "CVX", "HD", "MCD", "DIS",
    "NFLX", "AMD", "INTC", "ORCL", "CRM", "ADBE",
]


# Precomputed universe scores persist here so the leaderboard loads instantly
# and survives restarts (no re-scoring the whole universe every boot).
_UNIVERSE_FILE = Path(__file__).resolve().parent.parent / "data" / "universe_scores.json"


def _load_universe() -> None:
    try:
        if _UNIVERSE_FILE.exists():
            import json

            data = json.loads(_UNIVERSE_FILE.read_text())
            with _cache_lock:
                for t, payload in data.items():
                    _cache[t] = (time.time(), payload)
            logger.info("loaded %d precomputed universe scores", len(data))
    except Exception as e:
        logger.info("universe load failed: %s", e)


def _persist_universe() -> None:
    try:
        import json

        with _cache_lock:
            data = {t: p for t, (_, p) in _cache.items()}
        _UNIVERSE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _UNIVERSE_FILE.write_text(json.dumps(data))
    except Exception as e:
        logger.info("universe persist failed: %s", e)


def _seed_leaderboard() -> None:
    for t in _SEED_TICKERS:
        with _cache_lock:
            already = t in _cache
        if already:
            continue  # loaded from the persisted universe — don't re-score
        try:
            result = _engine.score_stock(t)
            if result is not None:
                payload = _serialize(result, cached=False)
                payload["name"] = _company_name(t)
                with _cache_lock:
                    _cache[t] = (time.time(), payload)
                _persist_universe()  # checkpoint after each new score
        except Exception as e:  # never let seeding crash the app
            logger.info("seed score failed for %s: %s", t, e)


@app.on_event("startup")
def _on_startup() -> None:
    _load_universe()
    Thread(target=_seed_leaderboard, daemon=True).start()


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
    payload["name"] = _company_name(ticker)
    with _cache_lock:
        _cache[ticker] = (now, payload)
    _persist_universe()
    return payload


# Serve the single-page frontend at the root.
if FRONTEND_DIR.exists():

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(FRONTEND_DIR / "index.html")

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR)), name="frontend")
