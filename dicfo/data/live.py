"""Live data fetchers. All free/public sources, no API keys.

Every fetcher fails soft: it returns what it could get plus an `errors` list,
so a blocked source never kills the report. The skills fill gaps with web search.
"""
from __future__ import annotations

import io
import datetime as dt

import pandas as pd
import requests

from ..analysis.technicals import metrics

UA = {"User-Agent": "Mozilla/5.0 (ai-cfo personal research tool)"}


def prices(symbols: list[str], period: str = "5y") -> tuple[dict, list[str]]:
    import yfinance as yf

    out, errors = {}, []
    try:
        data = yf.download(symbols, period=period, auto_adjust=True, progress=False,
                           group_by="ticker", threads=True)
    except Exception as e:  # network / rate limit
        return {}, [f"yfinance download failed: {e}"]
    for s in symbols:
        try:
            close = data[s]["Close"] if len(symbols) > 1 else data["Close"]
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            m = metrics(close)
            if m:
                out[s] = m
            else:
                errors.append(f"{s}: no prices")
        except Exception as e:
            errors.append(f"{s}: {e}")
    return out, errors


FUND_FIELDS = {
    "shortName": "name", "sector": "sector", "currency": "currency",
    "marketCap": "market_cap", "trailingPE": "pe", "forwardPE": "forward_pe",
    "pegRatio": "peg", "trailingPegRatio": "peg_trailing", "priceToBook": "pb",
    "returnOnEquity": "roe", "debtToEquity": "debt_to_equity",
    "profitMargins": "net_margin", "operatingMargins": "op_margin",
    "revenueGrowth": "revenue_growth", "earningsGrowth": "earnings_growth",
    "freeCashflow": "fcf", "trailingEps": "eps", "bookValue": "bvps",
    "dividendYield": "dividend_yield", "targetMeanPrice": "analyst_target",
    "recommendationKey": "analyst_view", "beta": "beta",
}


def fundamentals(symbols: list[str]) -> tuple[dict, list[str]]:
    import yfinance as yf

    out, errors = {}, []
    for s in symbols:
        try:
            info = yf.Ticker(s).info or {}
            row = {v: info.get(k) for k, v in FUND_FIELDS.items() if info.get(k) is not None}
            if "peg" not in row and "peg_trailing" in row:
                row["peg"] = row["peg_trailing"]
            # yfinance reports debtToEquity as a percentage (e.g. 45.2 = 0.452x)
            if row.get("debt_to_equity") is not None:
                row["debt_to_equity"] = row["debt_to_equity"] / 100
            out[s] = row
        except Exception as e:
            errors.append(f"{s} fundamentals: {e}")
    return out, errors


FRED = {
    "us_cpi_index": "CPIAUCSL",
    "fed_funds": "FEDFUNDS",
    "us_unemployment": "UNRATE",
    "us10y_fred": "DGS10",
    "us_real10y": "DFII10",
    "hy_spread": "BAMLH0A0HYM2",
}


def fred() -> tuple[dict, list[str]]:
    out, errors = {}, []
    for key, sid in FRED.items():
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}",
                             headers=UA, timeout=20)
            r.raise_for_status()
            df = pd.read_csv(io.StringIO(r.text))
            df.columns = ["date", "value"]
            df["value"] = pd.to_numeric(df["value"], errors="coerce")
            df = df.dropna()
            if key == "us_cpi_index":
                out["us_cpi_yoy"] = float(df["value"].iloc[-1] / df["value"].iloc[-13] - 1)
                out["us_cpi_date"] = df["date"].iloc[-1]
            else:
                out[key] = float(df["value"].iloc[-1]) / 100
        except Exception as e:
            errors.append(f"FRED {sid}: {e}")
    return out, errors


def mutual_funds(codes: dict) -> tuple[dict, list[str]]:
    out, errors = {}, []
    for code, label in codes.items():
        try:
            r = requests.get(f"https://api.mfapi.in/mf/{code}", headers=UA, timeout=20)
            r.raise_for_status()
            j = r.json()
            navs = pd.Series(
                [float(x["nav"]) for x in j["data"]],
                index=pd.to_datetime([x["date"] for x in j["data"]], dayfirst=True),
            ).sort_index()
            m = metrics(navs)
            m["name"] = j.get("meta", {}).get("scheme_name", label)
            m["category"] = j.get("meta", {}).get("scheme_category")
            out[code] = m
        except Exception as e:
            errors.append(f"MF {code}: {e}")
    return out, errors


def news(queries: list[str], per_query: int = 6) -> tuple[list[dict], list[str]]:
    import feedparser

    items, errors, seen = [], [], set()
    for q in queries:
        url = ("https://news.google.com/rss/search?q=" + requests.utils.quote(q + " when:3d")
               + "&hl=en-US&gl=US&ceid=US:en")
        try:
            r = requests.get(url, headers=UA, timeout=20)
            r.raise_for_status()
            feed = feedparser.parse(r.content)
            for e in feed.entries[:per_query]:
                if e.title in seen:
                    continue
                seen.add(e.title)
                items.append({"query": q, "title": e.title, "link": e.link,
                              "published": e.get("published", "")})
        except Exception as e:
            errors.append(f"news '{q}': {e}")
    return items, errors


def collect(universe: dict) -> dict:
    """Pull everything into one snapshot dict."""
    syms = set(universe["indices"].values()) | set(universe["macro_markets"].values())
    syms |= set(universe["asset_class_proxies"].values())
    for group in universe["stocks"].values():
        syms |= set(group)
    for group in universe["etfs"].values():
        syms |= set(group)
    stock_syms = [s for g in universe["stocks"].values() for s in g]

    snap = {"as_of": dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes"),
            "source": "live", "errors": []}
    snap["markets"], e1 = prices(sorted(syms))
    snap["fundamentals"], e2 = fundamentals(stock_syms)
    macro, e3 = fred()
    snap["mutual_funds"], e4 = mutual_funds(universe.get("mutual_funds", {}))
    snap["news"], e5 = news(universe.get("news_queries", []))
    snap["errors"] = e1 + e2 + e3 + e4 + e5

    mk = snap["markets"]
    pick = lambda s: mk.get(universe["macro_markets"].get(s) or universe["indices"].get(s), {})
    macro.update({
        "brent": pick("brent").get("price"),
        "brent_ret_3m": pick("brent").get("ret_3m"),
        "usdinr": pick("usdinr").get("price"),
        "usdinr_ret_1y": pick("usdinr").get("ret_1y"),
        "us_vix": pick("us_vix").get("price"),
        "india_vix": pick("india_vix").get("price"),
    })
    if pick("us10y").get("price"):
        macro["us10y"] = pick("us10y")["price"] / 100
    if pick("us3m").get("price"):
        macro["us3m"] = pick("us3m")["price"] / 100
    snap["macro"] = {k: v for k, v in macro.items() if v is not None}
    return snap
