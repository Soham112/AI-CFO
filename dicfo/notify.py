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


def _https(url: str):
    if not url.startswith("https://"):
        raise ValueError("refusing to send over a non-HTTPS connection")


def whatsapp(text: str) -> str:
    sid, tok = os.environ.get("TWILIO_ACCOUNT_SID"), os.environ.get("TWILIO_AUTH_TOKEN")
    if sid and tok:
        _https("https://api.twilio.com")
        r = requests.post(f"https://api.twilio.com/2010-04-01/Accounts/{sid}/Messages.json", auth=(sid, tok),
                          data={"From": os.environ["TWILIO_WHATSAPP_FROM"], "To": os.environ["TWILIO_WHATSAPP_TO"],
                                "Body": text[:1600]}, timeout=30)
        r.raise_for_status()
        return "whatsapp sent via Twilio"
    phone, key = os.environ.get("CALLMEBOT_PHONE"), os.environ.get("CALLMEBOT_APIKEY")
    if phone and key:
        r = requests.get("https://api.callmebot.com/whatsapp.php",
                         params={"phone": phone, "text": text[:1500], "apikey": key}, timeout=30)
        r.raise_for_status()
        return "whatsapp sent via CallMeBot"
    return "whatsapp skipped: set CALLMEBOT_* or TWILIO_* in .env"


def send(channels: list[str], subject: str, text: str, markdown: str) -> list[str]:
    out = []
    for c in channels:
        try:
            out.append(email(subject, text, markdown) if c == "email" else whatsapp(text) if c == "whatsapp"
                       else f"unknown channel {c}")
        except Exception as e:  # never crash the daily job on a notification failure
            out.append(f"{c} failed: {type(e).__name__}")   # no details: they can echo secrets
    return out
