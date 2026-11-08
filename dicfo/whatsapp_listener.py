"""Event-driven WhatsApp listener for the whatsapp-mcp bridge (github.com/verygoodplugins/whatsapp-mcp).

The bridge POSTs every incoming WhatsApp message to WEBHOOK_URL. This server receives
them on 127.0.0.1, and for ALLOWED senders only, runs a FIXED set of DICFO commands and
replies through the bridge. Nothing else can be triggered: no shell, no free-form AI.

Run:  python -m dicfo whatsapp-listen --profile dad
Env (.env):
  DICFO_WA_ALLOWED=19455440767            # comma list of phone numbers allowed to command DICFO
  DICFO_WA_BRIDGE_TOKEN=<contents of whatsapp-bridge/store/.bridge-token>
  DICFO_WA_BRIDGE_URL=http://127.0.0.1:8080/api/send
  DICFO_WA_PORT=8769
Bridge side: set WEBHOOK_URL=http://127.0.0.1:8769/whatsapp/webhook explicitly so it signs requests.
"""
from __future__ import annotations

import hmac
import json
import os
import re
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

TAG = "🤖 DICFO"
MAX_BODY = 64 * 1024
RATE = (20, 3600)            # max commands per window (seconds)
HELP = (f"{TAG} commands:\n"
        "brief - today's summary\n"
        "plan - this month's core and opportunistic status\n"
        "invested <amount> <fund or stock> - record a purchase, e.g. invested 10000 UTI Nifty\n"
        "help - this list\n"
        "Never send PAN, Aadhaar, account numbers or passwords here.")
# Shared by the WhatsApp and Telegram listeners.


def digits(s: str) -> str:
    return re.sub(r"\D", "", str(s or "").split("@")[0].split(":")[0])


def extract(payload: dict) -> dict:
    """Tolerant parser: bridge versions name fields differently."""
    msg = payload.get("message") if isinstance(payload.get("message"), dict) else payload
    get = lambda *ks: next((msg.get(k) for k in ks if msg.get(k) not in (None, "")), None)
    return {
        "id": get("id", "message_id", "ID"),
        "sender": digits(get("sender", "from", "sender_jid", "Sender") or ""),
        "chat": get("chat_jid", "chat", "chatJID", "ChatJID", "remote_jid") or "",
        "text": str(get("content", "text", "body", "Content", "message") or "").strip(),
        "event": payload.get("eventType") or payload.get("type") or "message",
    }


class Brain:
    """Pure command logic, separated from HTTP so it can be tested."""

    def __init__(self, profile: str | None, allowed: set[str], snapshot_loader=None):
        self.profile, self.allowed = profile, allowed
        self.seen: deque = deque(maxlen=500)
        self.calls: deque = deque()
        self.snapshot_loader = snapshot_loader

    def _rate_ok(self) -> bool:
        now = time.time()
        while self.calls and now - self.calls[0] > RATE[1]:
            self.calls.popleft()
        if len(self.calls) >= RATE[0]:
            return False
        self.calls.append(now)
        return True

    def _result(self):
        from . import config, ledger
        from .data import snapshot as sm
        from .engine import run
        path = sm.latest()
        if not path:
            raise RuntimeError("no market data yet (the daily fetch hasn't run)")
        snap = sm.load(path)
        day = str(snap.get("as_of", ""))[:10]
        for o in sorted(sm.SNAPSHOTS.glob(f"overrides-{day}-*.json")):
            snap = sm.deep_merge(snap, sm.load(o))
        name = config.profile_path(self.profile).stem
        return run(snap, config.load_profile(self.profile), ledger.load(name)), name

    def handle(self, m: dict) -> str | None:
        """Return reply text, or None to stay silent."""
        if m["event"] != "message" or not m["text"]:
            return None
        if m["text"].startswith(TAG):                     # our own reply echoed back: avoid loops
            return None
        if m["sender"] not in self.allowed:               # strangers get nothing, not even an error
            return None
        if m["id"]:
            if m["id"] in self.seen:
                return None
            self.seen.append(m["id"])
        words = m["text"].lower().split()
        cmd = words[0] if words else ""
        if cmd not in ("help", "brief", "summary", "plan", "invested"):
            return None                                   # ordinary chat: ignore silently
        if not self._rate_ok():
            return f"{TAG}: too many commands this hour; try later."
        from .security import scan
        if scan({"t": m["text"]}):
            return f"{TAG}: that message looks like it contains an ID or account number. Not processed. Please delete it."
        try:
            if cmd == "help":
                return HELP
            if cmd in ("brief", "summary"):
                from .report import summary
                r, _ = self._result()
                return f"{TAG}\n" + summary(r, redact=os.environ.get("DICFO_PRIVACY", "strict") != "off")
            if cmd == "plan":
                r, _ = self._result()
                mp = r["monthly_plan"]
                lines = [f"{TAG} plan {mp['month']}"]
                lines += [f"- {c['name']}: {c['verdict']}{' (recorded)' if not c['pending'] else ' (not recorded)'}"
                          for c in mp["core"]]
                lines += [f"- {o['name']}: {o['status']}" for o in mp["opportunistic"]]
                return "\n".join(lines)
            if cmd == "invested":
                return self._invested(m["text"])
        except Exception as e:
            return f"{TAG}: couldn't do that ({type(e).__name__}). Check the laptop."
        return None

    def _invested(self, text: str) -> str:
        mt = re.match(r"\s*invested\s+([\d,]+(?:\.\d+)?)\s*(?:rs\.?|inr|₹|\$)?\s+(?:in\s+)?(.+)$", text, re.I)
        if not mt:
            return f"{TAG}: format is: invested 10000 UTI Nifty"
        amt, what = float(mt.group(1).replace(",", "")), mt.group(2).strip().lower()
        r, name = self._result()
        core = r["monthly_plan"]["core"] + [{"symbol": o["symbol"], "name": o["name"], "monthly": None,
                                             "asset_class": o["asset_class"]} for o in r["monthly_plan"]["opportunistic"]]
        tokens = set(re.findall(r"\w+", what))
        best = max(core, key=lambda c: len(tokens & set(re.findall(r"\w+", c["name"].lower()))), default=None)
        if not best or not tokens & set(re.findall(r"\w+", best["name"].lower())):
            return f"{TAG}: couldn't match '{what}' to your plan. Use the name from 'plan', or record it on the laptop."
        from .ledger import add, validate_row
        planned = best.get("monthly")
        if not validate_row({"amount": amt}, planned, confirm=lambda _: "no"):
            return f"{TAG}: {amt:,.0f} looks unusual for {best['name']}. Record it on the laptop (python -m dicfo checkin)."
        add(name, [{"symbol": best["symbol"], "name": best["name"], "amount": amt,
                    "asset_class": best["asset_class"], "note": "whatsapp"}])
        return f"{TAG}: recorded {best['name']}. Thanks!"


def send(to_chat: str, text: str):
    url = os.environ.get("DICFO_WA_BRIDGE_URL", "http://127.0.0.1:8080/api/send")
    if not url.startswith(("http://127.0.0.1", "http://localhost")):
        raise ValueError("bridge must be on this computer")
    tok = os.environ.get("DICFO_WA_BRIDGE_TOKEN", "")
    requests.post(url, json={"recipient": to_chat, "message": text},
                  headers={"Authorization": f"Bearer {tok}"} if tok else {}, timeout=30).raise_for_status()


def make_handler(brain: Brain, token: str):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):          # don't log message contents
            pass

        def do_POST(self):
            if self.path.rstrip("/") != "/whatsapp/webhook":
                return self._done(404)
            got = self.headers.get("X-Bridge-Token", "")
            if not token or not hmac.compare_digest(got, token):
                return self._done(401)
            n = int(self.headers.get("Content-Length") or 0)
            if n > MAX_BODY:
                return self._done(413)
            try:
                m = extract(json.loads(self.rfile.read(n) or b"{}"))
            except ValueError:
                return self._done(400)
            self._done(200)                     # ack fast; reply afterwards
            reply = brain.handle(m)
            if reply:
                try:
                    send(m["chat"] or m["sender"], reply)
                except Exception as e:
                    print("send failed:", type(e).__name__)

        def _done(self, code):
            self.send_response(code)
            self.end_headers()
    return H


def serve(profile: str | None):
    token = os.environ.get("DICFO_WA_BRIDGE_TOKEN", "")
    allowed = {digits(x) for x in os.environ.get("DICFO_WA_ALLOWED", "").split(",") if digits(x)}
    if not token or not allowed:
        raise SystemExit("Set DICFO_WA_BRIDGE_TOKEN and DICFO_WA_ALLOWED in .env first (see docs/WHATSAPP.md).")
    port = int(os.environ.get("DICFO_WA_PORT", 8769))
    srv = ThreadingHTTPServer(("127.0.0.1", port), make_handler(Brain(profile, allowed), token))
    print(f"DICFO WhatsApp listener on 127.0.0.1:{port}, answering {len(allowed)} allowed number(s). Ctrl+C to stop.")
    srv.serve_forever()
