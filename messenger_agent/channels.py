"""Delivery channels: email over SMTP and WhatsApp over Meta's official Cloud API.

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

import httpx

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


# Meta error codes worth explaining in plain words.
_META_ERRORS = {
    131047: "More than 24 hours have passed since this person last messaged your WhatsApp business number, "
            "so WhatsApp only allows paid template messages. Ask them to send you any message first, then try again.",
    131030: "This number isn't on your test number's allowed list. Add it under WhatsApp > API Setup > "
            "'To' in the Meta developer dashboard (test numbers can message up to 5 people).",
    131026: "WhatsApp couldn't deliver to this number. Check that it's correct and has WhatsApp.",
    190: "Your WhatsApp access token is invalid or has expired. Create a new one and run --setup.",
}


def send_whatsapp(to: str, message: str, dry_run: bool = False) -> str:
    """Send a text message with Meta's official WhatsApp Cloud API.

    Free-form text only reaches people who messaged your business number in the last 24 hours.
    """
    if not PHONE_RE.match(to):
        raise ChannelError(f"'{to}' is not a phone number in international format (e.g. +14155550123).")
    cfg = _require_env("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")

    if dry_run:
        return f"[dry run] WhatsApp message to {to} was not sent."

    version = os.environ.get("WHATSAPP_API_VERSION", "v25.0")
    url = f"https://graph.facebook.com/{version}/{cfg['WHATSAPP_PHONE_NUMBER_ID']}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to.lstrip("+"),
        "type": "text",
        "text": {"body": message},
    }
    try:
        resp = httpx.post(url, json=payload, headers={"Authorization": f"Bearer {cfg['WHATSAPP_TOKEN']}"}, timeout=30)
    except httpx.HTTPError as exc:
        raise ChannelError(f"WhatsApp message to {to} failed: could not reach Meta ({exc}).") from exc

    try:
        data = resp.json()
    except ValueError:
        data = {}
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        code = err.get("code")
        detail = _META_ERRORS.get(code) or err.get("message") or f"HTTP {resp.status_code}"
        raise ChannelError(f"WhatsApp message to {to} failed: {detail}")
    msg_id = (data.get("messages") or [{}])[0].get("id", "?")
    return f"WhatsApp message sent to {to} (id: {msg_id})."


def check_whatsapp() -> str:
    """Confirm the WhatsApp token and phone number ID work, without sending anything."""
    cfg = _require_env("WHATSAPP_TOKEN", "WHATSAPP_PHONE_NUMBER_ID")
    version = os.environ.get("WHATSAPP_API_VERSION", "v25.0")
    try:
        resp = httpx.get(
            f"https://graph.facebook.com/{version}/{cfg['WHATSAPP_PHONE_NUMBER_ID']}",
            params={"fields": "display_phone_number,verified_name,quality_rating"},
            headers={"Authorization": f"Bearer {cfg['WHATSAPP_TOKEN']}"},
            timeout=30,
        )
        data = resp.json()
    except (httpx.HTTPError, ValueError) as exc:
        raise ChannelError(f"Could not reach Meta: {exc}") from exc
    if resp.status_code >= 400 or "error" in data:
        err = data.get("error", {})
        raise ChannelError(_META_ERRORS.get(err.get("code")) or err.get("message") or f"HTTP {resp.status_code}")
    return (f"WhatsApp OK: sending as {data.get('verified_name', '?')} "
            f"({data.get('display_phone_number', '?')}), quality rating {data.get('quality_rating', 'n/a')}.")


def check_email() -> str:
    """Log in to the mail server without sending anything."""
    cfg = _require_env("SMTP_HOST", "SMTP_USERNAME", "SMTP_PASSWORD")
    port = int(os.environ.get("SMTP_PORT", "587"))
    context = ssl.create_default_context()
    try:
        if port == 465:
            with smtplib.SMTP_SSL(cfg["SMTP_HOST"], port, context=context, timeout=30) as smtp:
                smtp.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
        else:
            with smtplib.SMTP(cfg["SMTP_HOST"], port, timeout=30) as smtp:
                smtp.starttls(context=context)
                smtp.login(cfg["SMTP_USERNAME"], cfg["SMTP_PASSWORD"])
    except (smtplib.SMTPException, OSError) as exc:
        raise ChannelError(f"Email login failed: {exc}") from exc
    return f"Email OK: logged in as {cfg['SMTP_USERNAME']}."


def load_contacts(path: str | os.PathLike[str] | None = None) -> list[dict]:
    path = Path(path or os.environ.get("CONTACTS_FILE", "contacts.json"))
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ChannelError(f"{path} must contain a JSON list of contacts.")
    return data
