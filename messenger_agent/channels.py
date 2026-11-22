"""Delivery channels: email over SMTP and WhatsApp over Twilio.

Credentials come from environment variables (see .env.example), so they stay on
your machine and are never sent to the model.
"""

from __future__ import annotations

import json
import os
import re
import smtplib
import ssl
from email.message import EmailMessage
from pathlib import Path

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^\+[1-9]\d{6,14}$")  # E.164, e.g. +14155550123


class ChannelError(Exception):
    """Raised when a message can't be sent; the text is shown to the agent."""


def _require_env(*names: str) -> dict[str, str]:
    missing = [n for n in names if not os.environ.get(n)]
    if missing:
        raise ChannelError(f"Missing configuration: {', '.join(missing)}. Add them to your .env file.")
    return {n: os.environ[n] for n in names}


def send_email(to: str, subject: str, body: str, dry_run: bool = False) -> str:
    if not EMAIL_RE.match(to):
        raise ChannelError(f"'{to}' is not a valid email address.")
    cfg = _require_env("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD")
    sender = os.environ.get("EMAIL_FROM") or cfg["SMTP_USERNAME"]
    port = int(os.environ.get("SMTP_PORT", "587"))

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    if dry_run:
        return f"[dry run] Email to {to} with subject '{subject}' was not sent."

    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(cfg["SMTP_HOST"], port, context=context, timeout=30) as smtp:
                smtp.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
                smtp.send_message(msg)
    except (smtplib.SMTPException, OSError) as exc:
        raise ChannelError(f"Email to {to} failed: {exc}") from exc
    return f"Email sent to {to}."


def send_whatsapp(to: str, message: str, dry_run: bool = False) -> str:
    if not PHONE_RE.match(to):
        raise ChannelError(f"'{to}' is not a phone number in international format (e.g. +14155550123).")
    cfg = _require_env("TWILIO_ACCOUNT_SID", "TWILIO_AUTH_TOKEN", "TWILIO_WHATSAPP_FROM")

    if dry_run:
        return f"[dry run] WhatsApp message to {to} was not sent."

    from twilio.base.exceptions import TwilioException
    from twilio.rest import Client

    sender = cfg["TWILIO_WHATSAPP_FROM"]
    if not sender.startswith("whatsapp:"):
        sender = f"whatsapp:{sender}"
    try:
        client = Client(cfg["TWILIO_ACCOUNT_SID"], cfg["TWILIO_AUTH_TOKEN"])
        result = client.messages.create(from_=sender, to=f"whatsapp:{to}", body=message)
    except TwilioException as exc:
        raise ChannelError(f"WhatsApp message to {to} failed: {exc}") from exc
    return f"WhatsApp message sent to {to} (status: {result.status}, id: {result.sid})."


def load_contacts(path: str | os.PathLike[str] | None = None) -> list[dict]:
    path = Path(path or os.environ.get("CONTACTS_FILE", "contacts.json"))
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ChannelError(f"{path} must contain a JSON list of contacts.")
    return data
