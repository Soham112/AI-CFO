"""Send the daily brief by email and/or WhatsApp. Secrets come from .env (never committed)."""
from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage

import requests


def email(subject: str, text: str, markdown: str | None = None) -> str:
    host, user = os.environ.get("DICFO_SMTP_HOST"), os.environ.get("DICFO_SMTP_USER")
    to = os.environ.get("DICFO_EMAIL_TO")
    if not (host and user and to):
        return "email skipped: set DICFO_SMTP_HOST / DICFO_SMTP_USER / DICFO_SMTP_PASS / DICFO_EMAIL_TO in .env"
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    full = os.environ.get("DICFO_EMAIL_FULL") == "1"
    msg.set_content(text)
    if markdown and full:
        msg.add_attachment(markdown.encode(), maintype="text", subtype="markdown", filename="dicfo-brief.md")
    import ssl
    with smtplib.SMTP(host, int(os.environ.get("DICFO_SMTP_PORT", 587)), timeout=30) as s:
        s.starttls(context=ssl.create_default_context())   # verifies the server certificate
        s.login(user, os.environ.get("DICFO_SMTP_PASS", ""))
        s.send_message(msg)
    return f"email sent to {to}"


def _https(url: str):  # noqa: D401
    if not url.startswith("https://"):
        raise ValueError("refusing to send over a non-HTTPS connection")


def telegram(text: str) -> str:
    """Official Telegram Bot API: free, no middleman, no 24-hour window rule."""
    tok, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not (tok and chat):
        return "telegram skipped: set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID in .env (see docs/INSTALL.md)"
    url = f"https://api.telegram.org/bot{tok}/sendMessage"
    _https(url)
    r = requests.post(url, data={"chat_id": chat, "text": text[:4000], "disable_web_page_preview": "true"},
                      timeout=30)
    r.raise_for_status()
    return "telegram sent"


def telegram_chat_id() -> str:
    """After you message your bot once, this finds your chat id."""
    tok = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not tok:
        return "Set TELEGRAM_BOT_TOKEN in .env first."
    r = requests.get(f"https://api.telegram.org/bot{tok}/getUpdates", timeout=30)
    r.raise_for_status()
    chats = {str(u["message"]["chat"]["id"]): u["message"]["chat"].get("first_name", "")
             for u in r.json().get("result", []) if "message" in u}
    if not chats:
        return "No messages yet: open your bot in Telegram, press Start / send 'hi', then run this again."
    return "\n".join(f"TELEGRAM_CHAT_ID={cid}   ({name})" for cid, name in chats.items())


def whatsapp(text: str) -> str:
    """WhatsApp via Twilio (an official Meta provider). Note WhatsApp's rule: free-form messages
    only arrive within 24 hours of the recipient's last message to the sender."""
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
    if not (sid and tok):
        return "whatsapp skipped: set TWILIO_* in .env"
    _https("https://api.twilio.com")
    body = text if len(text) <= 1600 else text[:text.rfind(chr(10), 0, 1600)]
    r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, tok),
                      data={"From": os.environ["TWILIO_WHATSAPP_FROM"], "To": os.environ["TWILIO_WHATSAPP_TO"],
                            "Body": body}, timeout=30)
    r.raise_for_status()
    return "whatsapp sent via Twilio"


def send(channels: list[str], subject: str, text: str, markdown: str) -> list[str]:
    out = []
    for c in channels:
        try:
            fn = {"email": lambda: email(subject, text, markdown), "telegram": lambda: telegram(text),
                  "whatsapp": lambda: whatsapp(text)}.get(c)
            out.append(fn() if fn else f"unknown channel {c}")
        except Exception as e:  # never crash the daily job on a notification failure
            out.append(f"{c} failed: {type(e).__name__}")   # no details: they can echo secrets
    return out
