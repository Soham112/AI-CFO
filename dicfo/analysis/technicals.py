"""Price-based signals computed from a daily close series."""
from __future__ import annotations

import math

import pandas as pd


def rsi(close: pd.Series, n: int = 14) -> float | None:
    if len(close) <= n:
        return None
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    last_loss = loss.iloc[-1]
    if last_loss == 0:
        return 100.0
    return float(100 - 100 / (1 + gain.iloc[-1] / last_loss))


def metrics(close: pd.Series) -> dict:
    """Summarise a close series into the fields the engine uses."""
    close = close.dropna()
    if close.empty:
        return {}
    last = float(close.iloc[-1])
    out = {"price": last}

    def ret(days):
        if len(close) > days:
            return float(last / close.iloc[-days - 1] - 1)
        return None

    out["chg_1d"] = ret(1)
    out["ret_1m"] = ret(21)
    out["ret_3m"] = ret(63)
    out["ret_1y"] = ret(252)
    out["ret_3y_cagr"] = ((last / close.iloc[-757]) ** (1 / 3) - 1) if len(close) > 757 else None
    year = close.iloc[-252:]
    out["high_52w"] = float(year.max())
    out["low_52w"] = float(year.min())
    out["off_high_52w"] = float(last / year.max() - 1)       # negative = below the high
    out["ath"] = float(close.max())
    out["off_ath"] = float(last / close.max() - 1)
    out["dma50"] = float(close.iloc[-50:].mean()) if len(close) >= 50 else None
    out["dma200"] = float(close.iloc[-200:].mean()) if len(close) >= 200 else None
    out["rsi14"] = rsi(close)
    daily = close.pct_change().dropna().iloc[-252:]
    out["vol_1y"] = float(daily.std() * math.sqrt(252)) if len(daily) > 20 else None
    return out


def trend(m: dict) -> str:
    p, d50, d200 = m.get("price"), m.get("dma50"), m.get("dma200")
    if not (p and d50 and d200):
        return m.get("trend_hint", "unknown")   # set by a web-search snapshot
    if p > d50 > d200:
        return "uptrend"
    if p < d50 < d200:
        return "downtrend"
    if p < d200:
        return "below_200dma"
    return "mixed"


def dip_score(m: dict) -> float:
    """-1..+2: how attractive the entry point is for a LONG-horizon buyer.

    Deeper drawdowns score higher (buy-the-dip), oversold RSI adds a bit,
    but a still-falling knife (down >30% and in downtrend) is capped so the
    engine stages entries instead of going all-in.
    """
    dd = m.get("off_high_52w")
    if dd is None:
        return 0.0
    if dd > -0.03:
        s = -0.5          # at/near highs: no discount
    elif dd > -0.08:
        s = 0.25
    elif dd > -0.15:
        s = 1.0           # correction territory
    elif dd > -0.25:
        s = 1.5
    else:
        s = 2.0           # bear market
    r = m.get("rsi14")
    if r is not None:
        if r < 30:
            s += 0.25
        elif r > 70:
            s -= 0.5
    if dd < -0.20 and trend(m) == "downtrend":
        s = min(s, 1.0)     # falling knife: still attractive, but only in small tranches
    return max(-1.0, min(2.0, s))
