# Stock Scorer

**Peer-relative fundamental scoring for US equities.** Enter a ticker and the
engine pulls its fundamentals, benchmarks every metric against a live,
sector-aware peer set, and returns a transparent **0–100 investment score**
across four weighted categories — with every underlying metric, percentile, and
contextual adjustment shown.

It is built around one principle: **a P/E of 28 means nothing in isolation.** It
only matters relative to the right peers. So instead of hard-coded thresholds,
Stock Scorer scores each metric by its *percentile rank within a computed peer
group*, then aggregates bottom-up into a single, explainable number.

```
 ┌──────────┐   ┌───────────────┐   ┌──────────────┐   ┌───────────────┐
 │  ticker  │ → │ peer discovery │ → │  percentile   │ → │ metric scoring │
 └──────────┘   │ + fundamentals │   │   ranking     │   │ (+ direction)  │
                └───────────────┘   └──────────────┘   └───────┬───────┘
                                                                │
 ┌──────────┐   ┌───────────────┐   ┌──────────────┐   ┌───────▼───────┐
 │ 0–100 +  │ ← │ final weighted │ ← │  contextual   │ ← │   category    │
 │ verdict  │   │     score      │   │ adjustments   │   │ aggregation   │
 └──────────┘   └───────────────┘   └──────────────┘   └───────────────┘
```

## Scoring methodology

**11 metrics → 4 categories → 1 score.**

| Category | Weight | Metrics |
|---|---|---|
| **Valuation** | 30% | P/E, PEG, Price/FCF |
| **Growth** | 25% | Revenue growth, EPS growth |
| **Profitability** | 25% | ROE, Operating margin, Net margin |
| **Risk** | 20% | Debt/Equity, Current ratio, Beta |

1. **Peer discovery** — for the target ticker, a sector/industry-aware peer set
   is assembled (cached in a local SQLite store) so comparisons are
   apples-to-apples.
2. **Percentile ranking** — each raw metric is converted to a percentile within
   the peer distribution (`scipy.stats.percentileofscore`).
3. **Direction-aware scoring** — "lower is better" metrics (P/E, debt, beta) are
   inverted so that *cheaper / safer = higher score*.
4. **Category aggregation** — metric scores roll up by intra-category weights.
5. **Contextual adjustments** — e.g. a high valuation is forgiven when growth
   justifies it; thin liquidity penalizes the risk score. Every adjustment is
   surfaced as a flag, never applied silently.
6. **Final weighted score** — categories combine into the 0–100 result with a
   plain-English rating and suggested action.

The whole pipeline is **glass-box**: the API and UI return every percentile and
per-metric score, so a number can always be traced back to its inputs.

## Quickstart

```bash
# 1. Install
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Run the API + web UI
uvicorn api.main:app --reload      # http://localhost:8000
```

Open <http://localhost:8000>, type a ticker (e.g. `AAPL`), and read the report.

## API

| Endpoint | Description |
|---|---|
| `GET /api/score/{ticker}` | Full scored report as JSON. `?refresh=true` bypasses the cache. |
| `GET /api/health` | Liveness check. |
| `GET /` | Single-page research frontend. |

```bash
curl http://localhost:8000/api/score/NVDA
```

```jsonc
{
  "ticker": "NVDA",
  "final_score": 71.4,
  "rating": "Good",
  "action": "Buy candidate - monitor key metrics",
  "categories": [
    { "name": "profitability", "score": 96.0, "weight": 0.25, "contribution": 24.0,
      "metrics": [ { "display_name": "ROE", "raw_value": 0.91, "percentile": 100, "score": 100 } ] }
  ],
  "warnings": ["Valuation elevated but supported by growth"],
  "peer_count": 6
}
```

Results are cached in-memory for one hour per ticker to avoid re-hitting the
upstream data provider.

## Testing

The pure-math core (percentiles, direction handling, aggregation, weighting,
interpretation) is covered by a fast, network-free suite:

```bash
pytest -q                 # 22 tests
pytest --cov=src          # with coverage
```

## Project structure

```
api/                 FastAPI service (score endpoint + static frontend)
frontend/            Single-page research UI (vanilla HTML/CSS/JS)
src/
  data/              yfinance client, peer manager, industry database
  scoring/           percentile → metric → category → adjustments → final
  scanning/          multi-ticker universe scanner
  backtesting/       historical score-vs-return analysis
  explanation/       natural-language report generation
  utils/             config (weights/metrics) + Pydantic models
tests/               unit tests for the scoring pipeline
```

## Tech

Python · FastAPI · pandas / numpy / scipy · yfinance · Pydantic · vanilla JS

## Disclaimer

For research and educational purposes only. **Not investment advice.** Scores
are relative to a computed peer set and depend on data availability from the
upstream provider.

## License

[MIT](LICENSE)
