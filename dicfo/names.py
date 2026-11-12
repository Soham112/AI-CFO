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
