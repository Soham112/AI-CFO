"""Company quality / value scoring plus investor-persona lenses.

Personas are encoded as transparent rule checklists, not impersonations: each
lens is a published investing philosophy turned into tests on the numbers.
"""
from __future__ import annotations

import math


def _num(x):
    return x if isinstance(x, (int, float)) and not math.isnan(x) else None


def graham_number(f: dict) -> float | None:
    eps, bv = _num(f.get("eps")), _num(f.get("bvps"))
    if eps and bv and eps > 0 and bv > 0:
        return math.sqrt(22.5 * eps * bv)
    return None


def is_financial(f: dict) -> bool:
    return bool(f.get("is_bank")) or "financial" in str(f.get("sector", "")).lower()


def quality_score(f: dict) -> float:
    """0..10 business quality: returns on capital, margins, balance sheet, growth.

    Banks are scored on ROE and margin only: leverage and 'free cash flow' are
    their raw material, not a warning sign.
    """
    if is_financial(f):
        roe, m = _num(f.get("roe")), _num(f.get("op_margin"))
        pts = (3 if roe and roe > 0.17 else 2 if roe and roe > 0.14 else 1 if roe and roe > 0.11 else 0)
        pts += (2 if m and m > 0.30 else 1 if m and m > 0.20 else 0)
        return round(pts / 5 * 10, 1)
    s = 0.0
    roe = _num(f.get("roe"))
    if roe is not None:
        s += 3 if roe > 0.20 else 2 if roe > 0.15 else 1 if roe > 0.10 else 0
    m = _num(f.get("op_margin"))
    if m is not None:
        s += 2 if m > 0.25 else 1 if m > 0.12 else 0
    de = _num(f.get("debt_to_equity"))
    if de is not None:
        s += 2 if de < 0.3 else 1 if de < 1.0 else 0
    g = _num(f.get("revenue_growth"))
    if g is not None:
        s += 2 if g > 0.12 else 1 if g > 0.05 else 0
    if _num(f.get("fcf")) and f["fcf"] > 0:
        s += 1
    return s


def value_score(f: dict, price: float | None, bond_yield: float | None) -> float:
    """-3..+3: is the price reasonable for what you get?"""
    s = 0.0
    fpe = _num(f.get("forward_pe")) or _num(f.get("pe"))
    if fpe and fpe > 0:
        ey = 1 / fpe
        if bond_yield:
            s += 1 if ey > bond_yield else -1 if ey < bond_yield * 0.6 else 0
        s += 1 if fpe < 18 else -1 if fpe > 35 else 0
    peg = _num(f.get("peg"))
    if peg and peg > 0:
        s += 1 if peg < 1.2 else -1 if peg > 2.5 else 0
    tgt = _num(f.get("analyst_target"))
    if tgt and price:
        up = tgt / price - 1
        s += 1 if up > 0.20 else -1 if up < 0 else 0
    return max(-3.0, min(3.0, s))


def lenses(f: dict, m: dict, bond_yield: float | None) -> dict:
    price = m.get("price")
    roe, de = _num(f.get("roe")), _num(f.get("debt_to_equity"))
    pe = _num(f.get("forward_pe")) or _num(f.get("pe"))
    peg = _num(f.get("peg"))
    gn = graham_number(f)
    out = {}
    out["buffett"] = {
        "philosophy": "Wonderful business at a fair price; durable moat, high ROE, little debt, hold for decades.",
        "checks": {
            "ROE > 15%": roe is not None and roe > 0.15,
            "Debt/Equity < 0.5": de is not None and de < 0.5,
            "Positive free cash flow": bool(_num(f.get("fcf")) and f["fcf"] > 0),
            "Earnings yield beats 10y bond": bool(pe and bond_yield and 1 / pe > bond_yield),
        },
    }
    out["graham"] = {
        "philosophy": "Margin of safety: pay well below intrinsic value.",
        "checks": {"Price below Graham number": bool(gn and price and price < gn)},
        "graham_number": gn,
    }
    out["lynch"] = {
        "philosophy": "Growth at a reasonable price; PEG under 1 is a bargain.",
        "checks": {"PEG < 1.2": bool(peg and 0 < peg < 1.2)},
    }
    out["jhunjhunwala_kamath_india_growth"] = {
        "philosophy": "Back India's consumption, financialisation and demographics for the long run; buy quality on fear.",
        "checks": {
            "Revenue growth > 12%": bool(_num(f.get("revenue_growth")) and f["revenue_growth"] > 0.12),
            "Bought on a >10% dip": bool(m.get("off_high_52w") is not None and m["off_high_52w"] < -0.10),
        },
    }
    out["damani"] = {
        "philosophy": "Patient value in simple consumer/retail businesses with clean balance sheets.",
        "checks": {
            "Low debt": de is not None and de < 0.3,
            "Op margin > 12%": bool(_num(f.get("op_margin")) and f["op_margin"] > 0.12),
        },
    }
    for v in out.values():
        c = v["checks"]
        v["passed"] = f"{sum(bool(x) for x in c.values())}/{len(c)}"
    return out


def analyse_stock(sym: str, f: dict, m: dict, bond_yield: float | None) -> dict:
    from .technicals import dip_score, trend

    q = quality_score(f)
    v = value_score(f, m.get("price"), bond_yield)
    d = dip_score(m)
    # Quality dominates: a cheap bad business is not an opportunity.
    composite = round(q * 0.5 + v * 0.8 + d * 1.0, 2)
    if q >= 7 and (v >= 1 or d >= 1):
        action = "ACCUMULATE (staged)"
    elif q >= 6 and v >= 0:
        action = "HOLD / SIP"
    elif q < 4:
        action = "AVOID"
    else:
        action = "WATCH"
    return {
        "symbol": sym, "name": f.get("name", sym), "price": m.get("price"),
        "off_high_52w": m.get("off_high_52w"), "trend": trend(m),
        "quality": q, "value": v, "dip": d, "composite": composite, "action": action,
        "pe": f.get("pe"), "forward_pe": f.get("forward_pe"), "roe": f.get("roe"),
        "lenses": lenses(f, m, bond_yield),
    }
