---
name: cfo-market-data
description: Fetch or reconstruct the DICFO market snapshot (prices, 52w highs, macro, rates, FX, MF NAVs). Use when `python -m dicfo fetch` fails or data is missing/stale.
---

# Market data

## Primary (free, no keys)
| Data | Source | Code |
|---|---|---|
| Prices, 52w high, DMA, RSI | Yahoo Finance via `yfinance` | `dicfo/data/live.py:prices` |
| Fundamentals | Yahoo `Ticker.info` | `fundamentals` |
| US CPI, Fed funds, real yields, HY spread | FRED CSV | `fred` |
| Indian MF NAVs | api.mfapi.in (AMFI) | `mutual_funds` |
| Headlines | Google News RSS | `news` |

Optional paid/connector upgrades (better fundamentals and estimates): Claude connectors for
FactSet, Morningstar, Financial Modeling Prep, Alpha Vantage, Financial Datasets. If one is
connected, prefer it for fundamentals and analyst estimates.

## Fallback: build a facts override from web search
When a source is blocked, search the web and write `snapshots/overrides-<date>-facts.json`:

```json
{
  "as_of": "2026-11-06",
  "source": "web-search",
  "markets": {
    "^GSPC": {"price": 7400, "high_52w": 7819, "off_high_52w": -0.054, "chg_1d": 0.006},
    "^NSEI": {"price": 25030, "high_52w": 26300, "off_high_52w": -0.048}
  },
  "macro": {"us_cpi_yoy": 0.037, "fed_funds": 0.04, "us10y": 0.0486, "india_cpi_yoy": 0.0554,
            "india_repo": 0.055, "usdinr": 94.07, "brent": 98.0, "us_vix": 24.3},
  "fundamentals": {"GOOGL": {"forward_pe": 22, "roe": 0.32, "...": "..."}},
  "notes": ["S&P 500 level from <url>"]
}
```

Rules: compute `off_high_52w = price / high_52w - 1` yourself; use decimals for percentages;
put every source URL in `notes`; never invent a number, leave the field out instead.
