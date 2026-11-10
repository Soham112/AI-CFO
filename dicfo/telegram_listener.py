"""Two-way Telegram bot ("AI Personal CFO") using long polling: no server, no open port.

Built for non-technical users: one plain-English message a day, and simple replies:
  today · month · done <SIP name> · invested <amount> <name> · help · /setup
Only allow-listed chats get answers; everything else is ignored.

Run:  python -m dicfo telegram-listen --profile dad
Env:  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (comma list), optional TELEGRAM_DETAIL_CHAT_ID
"""
from __future__ import annotations

import json
import os
import re
import time

import requests

from . import friendly
from .whatsapp_listener import Brain

API = "https://api.telegram.org/bot{tok}/{method}"


def _call(tok: str, method: str, **data):
    r = requests.post(API.format(tok=tok, method=method), data=data, timeout=30)
    r.raise_for_status()
    return r.json()


def send_card(tok: str, chat: str, card: dict):
    data = {"chat_id": chat, "text": card["text"][:4000], "disable_web_page_preview": "true"}   # plain text
    if card.get("buttons"):
        data["reply_markup"] = json.dumps({"inline_keyboard": [[{"text": l, "callback_data": d[:64]} for l, d in row]
                                                               for row in card["buttons"]]})
    return _call(tok, "sendMessage", **data)


def _esc(s: str) -> str:
    return s      # messages are sent as plain text, nothing to escape


def to_message(update: dict) -> dict | None:
    """Plain text message -> the shape Brain expects (kept for text commands)."""
    m = update.get("message") or update.get("edited_message")
    if not m:
        return None
    return {"id": f"tg{update['update_id']}", "sender": str(m.get("chat", {}).get("id", "")),
            "chat": str(m.get("chat", {}).get("id", "")), "text": (m.get("text") or "").strip(),
            "event": "message", "date": m.get("date", 0)}


class Bot:
    def __init__(self, profile_name: str | None, allowed: set[str], tok: str = ""):
        self.profile_name, self.allowed, self.tok = profile_name, allowed, tok
        self.brain = Brain(profile_name, allowed)
        self.awaiting_amount: dict[str, str] = {}      # chat -> symbol
        self.onboarding: dict = {}                    # chat -> Onboarding
        self.out: list[tuple[str, dict]] = []         # (chat, card) when no token (tests)

    # ---------- helpers ----------
    def _send(self, chat, card):
        if self.tok:
            send_card(self.tok, chat, card)
        else:
            self.out.append((chat, card))

    def _profile(self) -> dict | None:
        from . import config
        try:
            return config.load_profile(self.profile_name)
        except SystemExit:
            return None

    def _result(self):
        return self.brain._result()

    def _item(self, r, sym):
        mp = r["monthly_plan"]
        return next((x for x in mp["core"] + mp["opportunistic"] if str(x["symbol"]) == str(sym)), None)

    def _record(self, chat, sym, amount, note) -> str:
        from .ledger import add, validate_row
        r, name = self._result()
        p = self._profile() or {}
        lang = p.get("language", "en")
        item = self._item(r, sym)
        if not item:
            return "Sorry, I couldn't find that in your plan."
        if not validate_row({"amount": amount}, item.get("monthly"), confirm=lambda _: "no"):
            return friendly.t(lang, "bad_amount")
        add(name, [{"symbol": sym, "name": item["name"], "amount": amount, "asset_class": item["asset_class"],
                    "note": note}])
        return friendly.t(lang, "recorded", name=item["name"], amt=friendly.money(amount, r.get("currency", "INR")))

    # ---------- entry points ----------
    def on_text(self, chat: str, text: str, update_id=None):
        if chat not in self.allowed:
            return
        from .security import scan
        if scan({"t": text}):
            return self._send(chat, {"text": "⚠️ That looks like an ID or account number. I didn't save it. "
                                              "Please delete that message.", "buttons": []})
        low = text.strip().lower()
        if chat in self.onboarding:
            return self._onboard_answer(chat, text)
        if chat in self.awaiting_amount:
            n = low.replace(",", "").replace("₹", "").replace("rs", "").strip()
            if n.replace(".", "", 1).isdigit():
                sym = self.awaiting_amount.pop(chat)
                return self._send(chat, {"text": self._record(chat, sym, float(n), "telegram"), "buttons": []})
        if low in ("/setup", "setup"):
            return self._start_onboarding(chat)
        if self._profile() is None:
            return self._start_onboarding(chat)
        if low in ("/start", "hi", "hello", "menu", "/menu", "namaste", "help", "/help"):
            return self._send(chat, {"text": _esc(friendly.SIMPLE_HELP), "buttons": []})
        if low in ("brief", "today", "/today", "summary"):
            return self._today(chat)
        if low in ("plan", "month", "/month"):
            return self._month(chat)
        if low.startswith("done "):
            return self._done(chat, low[5:].strip())
        reply = self.brain.handle({"id": f"tg{update_id}", "sender": chat, "chat": chat, "text": text,
                                   "event": "message"})
        self._send(chat, {"text": _esc(reply) if reply else _esc(friendly.SIMPLE_HELP), "buttons": []})

    def on_button(self, chat: str, data: str) -> str:
        """Handle a button tap. Returns a short toast text."""
        if chat not in self.allowed:
            return ""
        parts = data.split("|")
        kind = parts[0]
        if kind == "q":
            return self._onboard_answer(chat, parts[2], from_button=int(parts[1])) or ""
        p = self._profile() or {}
        lang = p.get("language", "en")
        if kind == "m":
            {"today": self._today, "month": self._month,
             "help": lambda c: self._send(c, {"text": friendly.t(lang, "help"), "buttons": []})}[parts[1]](chat)
            return ""
        r, _ = self._result()
        sym = parts[1]
        item = self._item(r, sym) or {"name": sym}
        if kind in ("b", "y"):
            msg = self._record(chat, sym, float(parts[2]), "telegram-button")
        elif kind == "s":
            msg = friendly.t(lang, "skipped", name=item["name"])
        elif kind == "n":
            msg = friendly.t(lang, "noted_no", name=item["name"])
        elif kind == "o":
            self.awaiting_amount[chat] = sym
            msg = friendly.t(lang, "ask_amount", name=item["name"])
        elif kind == "w":
            msg = friendly.why(r, sym, p)
        else:
            return ""
        self._send(chat, {"text": msg, "buttons": []})
        return "✓"

    # ---------- flows ----------
    def _today(self, chat):
        r, _ = self._result()
        self._send(chat, {"text": _esc(friendly.simple_message(r, self._profile())), "buttons": []})

    def _month(self, chat):
        r, _ = self._result()
        self._send(chat, {"text": _esc(friendly.simple_month(r, self._profile())), "buttons": []})

    def _done(self, chat, what: str):
        """'done UTI Nifty' marks this month's SIP as paid at its planned amount."""
        import re as _re
        r, _ = self._result()
        tokens = set(_re.findall(r"\w+", what))
        core = r["monthly_plan"]["core"]
        best = max(core, key=lambda c: len(tokens & set(_re.findall(r"\w+", c["name"].lower()))), default=None)
        if not best or not tokens & set(_re.findall(r"\w+", best["name"].lower())):
            names = ", ".join(c["name"] for c in core)
            return self._send(chat, {"text": _esc(f"I couldn't find '{what}'. Your SIPs are: {names}"), "buttons": []})
        if not best["pending"]:
            return self._send(chat, {"text": _esc(f"{best['name']} is already marked done this month ✅"), "buttons": []})
        self._send(chat, {"text": _esc(self._record(chat, best["symbol"], best["pending"], "telegram-done")), "buttons": []})

    def _start_onboarding(self, chat):
        from .chat_onboard import Onboarding
        self.onboarding[chat] = Onboarding()
        self._send(chat, {"text": "Let's set up your Personal CFO. It takes about 2 minutes. 🙂\n"
                                  "Never send PAN, Aadhaar, account numbers or passwords.", "buttons": []})
        self._send(chat, self.onboarding[chat].current())

    def _onboard_answer(self, chat, value, from_button=None):
        ob = self.onboarding[chat]
        if from_button is not None and from_button != ob.i:
            return ""                                  # stale button from an earlier question
        err = ob.answer(value)
        if err:
            self._send(chat, {"text": err, "buttons": []})
            return ""
        if ob.finished():
            from .chat_onboard import save
            from .config import profile_path
            try:
                save(profile_path(self.profile_name).stem, ob.profile())
                done = ("All set ✅ I'll message you when there's something to do. Tap below any time.")
            except Exception as e:
                done = f"I couldn't save that ({e}). Please ask Soh to check the laptop."
            del self.onboarding[chat]
            self._send(chat, {"text": done, "buttons": []})
            if self._profile():
                self._send(chat, {"text": friendly.SIMPLE_HELP, "buttons": []})
        else:
            self._send(chat, ob.current())
        return ""


def push_daily(r: dict, profile: dict) -> str:
    """Send today's cards to the first allowed chat; detailed summary to TELEGRAM_DETAIL_CHAT_ID if set."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    chats = [x.strip() for x in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if x.strip()]
    if not (tok and chats):
        return "telegram skipped: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env"
    send_card(tok, chats[0], {"text": _esc(friendly.simple_message(r, profile)), "buttons": []})
    detail = os.environ.get("TELEGRAM_DETAIL_CHAT_ID")
    if detail:
        from .report import summary
        send_card(tok, detail, {"text": summary(r, redact=False), "buttons": []})
    return "telegram sent"


def listen(profile: str | None, once: bool = False):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    allowed = {x.strip() for x in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if x.strip()}
    if not tok or not allowed:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env (run `python -m dicfo telegram-id`).")
    bot = Bot(profile, allowed, tok)
    started, offset, backoff = time.time(), None, 1
    print(f"AI Personal CFO listening for {len(allowed)} allowed chat(s). Ctrl+C to stop.")
    while True:
        try:
            r = requests.get(API.format(tok=tok, method="getUpdates"),
                             params={"timeout": 50, "offset": offset,
                                     "allowed_updates": '["message","callback_query"]'}, timeout=60)
            r.raise_for_status()
            backoff = 1
            for u in r.json().get("result", []):
                offset = u["update_id"] + 1
                try:
                    if "callback_query" in u:
                        cq = u["callback_query"]
                        chat = str(cq["message"]["chat"]["id"])
                        toast = bot.on_button(chat, cq.get("data", ""))
                        _call(tok, "answerCallbackQuery", callback_query_id=cq["id"], text=toast or "")
                        if chat in bot.allowed:   # remove buttons so a tap can't be repeated
                            _call(tok, "editMessageReplyMarkup", chat_id=chat, message_id=cq["message"]["message_id"],
                                  reply_markup=json.dumps({"inline_keyboard": []}))
                        continue
                    m = to_message(u)
                    if not m or m["date"] < started - 60:
                        continue
                    bot.on_text(m["chat"], m["text"], u["update_id"])
                except Exception as e:                  # one bad update must not stop the bot
                    print("update error:", type(e).__name__, e)
            if once:
                return
        except KeyboardInterrupt:
            return
        except Exception as e:
            print("telegram poll error:", type(e).__name__)
            time.sleep(min(backoff, 300))
            backoff *= 2
