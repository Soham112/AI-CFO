"""Turn a company name typed by a person ("HDFC Bank", "Infosys", "reliance industries") into an NSE symbol."""
from __future__ import annotations

import re

ALIASES = {
    "hdfc bank": "HDFCBANK", "icici bank": "ICICIBANK", "icici": "ICICIBANK", "infosys": "INFY",
    "tata consultancy": "TCS", "airtel": "BHARTIARTL", "bharti airtel": "BHARTIARTL", "larsen": "LT",
    "l&t": "LT", "larsen and toubro": "LT", "sbi": "SBIN", "state bank": "SBIN", "state bank of india": "SBIN",
    "kotak": "KOTAKBANK", "kotak bank": "KOTAKBANK", "kotak mahindra bank": "KOTAKBANK", "axis bank": "AXISBANK",
    "hul": "HINDUNILVR", "hindustan unilever": "HINDUNILVR", "bajaj finance": "BAJFINANCE",
    "bajaj finserv": "BAJAJFINSV", "bajaj auto": "BAJAJ-AUTO", "mahindra": "M&M", "m&m": "M&M",
    "mahindra and mahindra": "M&M", "maruti": "MARUTI", "maruti suzuki": "MARUTI", "sun pharma": "SUNPHARMA",
    "hcl": "HCLTECH", "hcl tech": "HCLTECH", "hcl technologies": "HCLTECH", "ultratech": "ULTRACEMCO",
    "ultratech cement": "ULTRACEMCO", "tata motors": "TMPV", "tata motors pv": "TMPV",
    "tata motors passenger": "TMPV", "tata motors cv": "TMCV", "tata motors commercial": "TMCV",
    "power grid": "POWERGRID", "asian paints": "ASIANPAINT", "adani enterprises": "ADANIENT",
    "adani ports": "ADANIPORTS", "nestle": "NESTLEIND", "nestle india": "NESTLEIND", "jsw steel": "JSWSTEEL",
    "tata steel": "TATASTEEL", "coal india": "COALINDIA", "tech mahindra": "TECHM", "grasim": "GRASIM",
    "hindalco": "HINDALCO", "dr reddy": "DRREDDY", "dr reddys": "DRREDDY", "dr. reddy's": "DRREDDY",
    "sbi life": "SBILIFE", "hdfc life": "HDFCLIFE", "eicher": "EICHERMOT", "eicher motors": "EICHERMOT",
    "bharat electronics": "BEL", "apollo hospitals": "APOLLOHOSP", "apollo": "APOLLOHOSP",
    "shriram finance": "SHRIRAMFIN", "indusind": "INDUSINDBK", "indusind bank": "INDUSINDBK",
    "hero": "HEROMOTOCO", "hero motocorp": "HEROMOTOCO", "britannia": "BRITANNIA", "tata consumer": "TATACONSUM",
    "zomato": "ETERNAL", "eternal": "ETERNAL", "reliance": "RELIANCE", "reliance industries": "RELIANCE",
    "itc": "ITC", "ongc": "ONGC", "ntpc": "NTPC", "titan": "TITAN", "trent": "TRENT", "cipla": "CIPLA",
    "wipro": "WIPRO", "tcs": "TCS",
}
_SUFFIX = re.compile(r"\b(ltd|limited|ltd\.|industries ltd|share|shares|equity)\b\.?", re.I)


def to_symbol(name: str, known: list[str] | None = None) -> tuple[str | None, bool]:
    """Return (symbol like 'HDFCBANK.NS', sure). sure=False means a best guess from a ticker-looking name."""
    n = _SUFFIX.sub("", name.lower()).strip(" .")
    n = re.sub(r"\s+", " ", n)
    if n in ALIASES:
        return ALIASES[n] + ".NS", True
    bases = {s.upper().removesuffix(".NS"): s.upper() for s in (known or [])}
    key = n.replace(" ", "").upper()
    if key in bases:
        return bases[key], True
    if re.fullmatch(r"[A-Z0-9&-]{2,15}", key) and " " not in n:   # looks like a ticker someone typed (e.g. IRCTC)
        return key + ".NS", False
    return None, False


def suggest(name: str, known: list[str] | None = None) -> str | None:
    """Closest known company name, for 'Did you mean ...?'."""
    import difflib
    n = _SUFFIX.sub("", name.lower()).strip(" .")
    pool = list(ALIASES) + [s.lower().removesuffix(".ns") for s in (known or [])]
    hit = difflib.get_close_matches(n, pool, n=1, cutoff=0.6) or \
        difflib.get_close_matches(n.replace(" ", ""), pool, n=1, cutoff=0.6)
    return hit[0].upper() if hit and len(hit[0]) <= 5 else (hit[0].title() if hit else None)


def resolve(name: str, known: list[str] | None = None, priced: set | None = None) -> tuple[str | None, str]:
    """(symbol, '') only when we're sure it's a real company; else (None, a polite message asking to retype)."""
    sym, sure = to_symbol(name, known)
    if sym and (sure or sym in (priced or set())):
        return sym, ""
    s = suggest(name, known)
    hint = f" Did you mean {s}?" if s else ""
    return None, (f"I don't know a company called '{name.strip()}', so I didn't save it.{hint} "
                  f"Please send it again with the right name, like: TCS 10")
