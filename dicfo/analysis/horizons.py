"""Short / medium / long term views for any asset or stock.

short  (1-3 months): trend, momentum, RSI, news. Used for TIMING of buys, never for trading.
medium (3-12 months): macro drivers + valuation + earnings momentum.
long   (3+ years):   business quality, valuation, structural story.
"""
from __future__ import annotations

from .technicals import trend


def _label(x: float) -> str:
    return "bullish" if x >= 0.5 else "bearish" if x <= -0.5 else "neutral"


def short_term(m: dict, news: float = 0.0) -> float:
    s = 0.0
    t = trend(m)
    s += {"uptrend": 0.75, "mixed": 0.0, "below_200dma": -0.25, "downtrend": -0.75}.get(t, 0.0)
    r1m = m.get("ret_1m")
    if r1m is not None:
        s += 0.5 if r1m > 0.05 else -0.5 if r1m < -0.05 else 0
    rsi = m.get("rsi14")
    if rsi is not None:
        s += 0.5 if rsi < 30 else -0.5 if rsi > 70 else 0     # stretched both ways tends to snap back
    return s + news


def asset_views(scores: dict) -> dict:
    out = {}
    for a, s in scores.items():
        m = s.get("proxy_metrics") or {}
        news = sum(v for k, v in s["drivers"].items() if k.startswith(("news:", "judgement:"))) * 0.5
        st = short_term(m, news) if m else news
        med = s["macro"] + 0.5 * s["dip"]
        out[a] = {"short": _label(st), "medium": _label(med), "long": None, "short_score": round(st, 2),
                  "medium_score": round(med, 2)}
    return out


def stock_views(r: dict, m: dict) -> dict:
    st = short_term(m)
    med = r["value"] * 0.5 + r["dip"] * 0.5
    lng = (r["quality"] - 5) / 2.5 + r["value"] * 0.25
    return {"short": _label(st), "medium": _label(med), "long": _label(lng)}
