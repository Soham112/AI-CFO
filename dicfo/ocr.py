"""Read mutual-fund holdings from a screenshot, on this computer only.

Text recognition uses macOS's built-in Vision framework (the engine behind Live Text), so the picture never
leaves the Mac and no AI service sees it. The result is always shown to the person to confirm before saving.
"""
from __future__ import annotations

import re
import sys

FUND_WORDS = re.compile(r"\b(fund|plan|growth|idcw|direct|regular|index|flexi|cap|elss|tax saver|nifty|sensex|"
                        r"bluechip|hybrid|balanced|debt|liquid|equity|fof|etf)\b", re.I)
MONEY = re.compile(r"(?:₹|rs\.?|inr)?\s*(-?[\d,]+(?:\.\d+)?)\s*([kl]|lakh|lac|cr)?\b", re.I)
CUR_W = re.compile(r"\b(current|market value|present value|value|worth|cur\.?\s*val)\b", re.I)
INV_W = re.compile(r"\b(invested|investment|cost|amount invested|principal)\b", re.I)
SKIP_W = re.compile(r"(%|xirr|returns?\b|gain|p&l|profit|loss|nav\b|units?\b|folio|day'?s?|1d|today|abs)", re.I)


def image_text(data: bytes) -> list[str]:
    """Lines of text, top to bottom."""
    if sys.platform != "darwin":
        raise ValueError("Reading screenshots works only on the Mac that runs the bot.")
    import Vision
    from Foundation import NSData
    req = Vision.VNRecognizeTextRequest.alloc().init()
    req.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
    req.setUsesLanguageCorrection_(False)
    try:
        req.setRecognitionLanguages_(["en-IN", "en-US"])
    except Exception:
        pass
    handler = Vision.VNImageRequestHandler.alloc().initWithData_options_(NSData.dataWithBytes_length_(data, len(data)), None)
    ok, err = handler.performRequests_error_([req], None)
    if not ok:
        raise ValueError("I couldn't read that picture. Please send a clear screenshot.")
    obs = sorted(req.results() or [], key=lambda o: (-o.boundingBox().origin.y, o.boundingBox().origin.x))
    return [o.topCandidates_(1)[0].string() for o in obs if o.topCandidates_(1)]


def _amount(s: str) -> float | None:
    if SKIP_W.search(s):
        return None
    best = None
    for m in MONEY.finditer(s):
        raw = m.group(1).replace(",", "")
        if not raw.strip("-.") or not any(ch.isdigit() for ch in raw):
            continue
        v = float(raw)
        unit = (m.group(2) or "").lower()
        v *= {"k": 1e3, "l": 1e5, "lakh": 1e5, "lac": 1e5, "cr": 1e7}.get(unit, 1)
        if v >= 100 and (best is None or "," in m.group(1) or unit):
            best = v
    return best


TOKEN = re.compile(r"(?:(?<=\s)|^)(?P<pre>[^\d\s,.+\-%()]?)(?P<num>\d[\d,]*(?:\.\d+)?)")


def fix_rupee(lines: list[str]) -> list[str]:
    """OCR often reads the ₹ sign as '7', 'Z', 'R' or '·'. If this screen writes ₹ before its amounts,
    a leading 7 on an amount with no other sign in front is really the ₹ sign: drop it."""
    toks = [m for ln in lines for m in TOKEN.finditer(ln) if "," in m["num"]]
    if not toks:
        return lines
    marked = [m for m in toks if m["pre"]]
    sevens = [m for m in toks if not m["pre"] and m["num"].startswith("7")]
    if not marked or (len(marked) + len(sevens)) / len(toks) < 0.6:
        return lines

    def strip7(m):
        n = m["num"]
        if not m["pre"] and n.startswith("7") and len(n.replace(",", "")) > 3:
            return n[1:].lstrip(",")
        return m["pre"] + n if m["pre"] else n
    return [TOKEN.sub(strip7, ln) for ln in lines]


def parse_funds(lines: list[str]) -> list[dict]:
    """Group recognised lines into funds: a name line, then labelled amounts (current / invested)."""
    funds, cur, want = [], None, None
    for raw in fix_rupee(lines):
        s = raw.strip()
        if not s:
            continue
        letters = sum(ch.isalpha() for ch in s)
        if FUND_WORDS.search(s) and letters >= 8 and letters > sum(ch.isdigit() for ch in s):
            if cur and cur["name"] and not (cur["current"] or cur["invested"]):
                cur["name"] += " " + s          # a long fund name wrapped onto two lines
                continue
            cur = {"name": s, "current": None, "invested": None}
            funds.append(cur)
            want = None
            continue
        if cur is None:
            continue
        label = "invested" if INV_W.search(s) else "current" if CUR_W.search(s) else None
        amt = None if (label is None and SKIP_W.search(s)) else _amount(re.sub(INV_W.pattern + "|" + CUR_W.pattern, "", s, flags=re.I))
        if label and amt is None:
            want = label                          # label on one line, number on the next
            continue
        if amt is None:
            continue
        key = label or want or ("current" if cur["current"] is None else "invested" if cur["invested"] is None else None)
        if key and cur[key] is None:
            cur[key] = amt
        want = None
    out = []
    for f in funds:
        name = re.sub(r"\s+", " ", f["name"]).strip(" -•")
        if f["current"] or f["invested"]:
            out.append({"name": name, "value": round(f["current"] or f["invested"]),
                        "invested": round(f["invested"]) if f["invested"] else None})
    return out
