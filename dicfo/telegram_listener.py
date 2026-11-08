"""Two-way Telegram bot using long polling: no server, no open port, no public URL.

The laptop keeps one outgoing HTTPS request open to Telegram; when an allowed person
messages the bot it returns immediately and the same fixed commands as the WhatsApp
listener run (brief, plan, invested <amount> <name>, help). Strangers are ignored.

Run:  python -m dicfo telegram-listen --profile dad
Env:  TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (comma list allowed; first one also gets the daily brief)
"""
from __future__ import annotations

import os
import time

import requests

from .whatsapp_listener import Brain

API = "https://api.telegram.org/bot{tok}/{method}"


def to_message(update: dict) -> dict | None:
    m = update.get("message") or update.get("edited_message")
    if not m:
        return None
    return {"id": f"tg{update['update_id']}", "sender": str(m.get("chat", {}).get("id", "")),
            "chat": str(m.get("chat", {}).get("id", "")), "text": (m.get("text") or "").strip(),
            "event": "message", "date": m.get("date", 0)}


def reply(tok: str, chat: str, text: str):
    requests.post(API.format(tok=tok, method="sendMessage"),
                  data={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": "true"},
                  timeout=30).raise_for_status()


def listen(profile: str | None, once: bool = False):
    tok = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    allowed = {x.strip() for x in os.environ.get("TELEGRAM_CHAT_ID", "").split(",") if x.strip()}
    if not tok or not allowed:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env (run `python -m dicfo telegram-id`).")
    brain = Brain(profile, allowed)
    started, offset, backoff = time.time(), None, 1
    print(f"DICFO Telegram listener running for {len(allowed)} allowed chat(s). Ctrl+C to stop.")
    while True:
        try:
            r = requests.get(API.format(tok=tok, method="getUpdates"),
                             params={"timeout": 50, "offset": offset, "allowed_updates": '["message"]'}, timeout=60)
            r.raise_for_status()
            backoff = 1
            for u in r.json().get("result", []):
                offset = u["update_id"] + 1
                m = to_message(u)
                if not m or m["date"] < started - 60:      # ignore backlog from while it was off
                    continue
                text = brain.handle(m)
                if text:
                    reply(tok, m["chat"], text)
            if once:
                return
        except KeyboardInterrupt:
            return
        except Exception as e:                              # network blips: back off, never crash
            print("telegram poll error:", type(e).__name__)
            time.sleep(min(backoff, 300))
            backoff *= 2
