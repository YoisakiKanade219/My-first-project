"""First-run setup: asks for your keys and saves them to a local .env file."""

from __future__ import annotations

import os
import shutil
from getpass import getpass
from pathlib import Path

from dotenv import set_key

ENV_PATH = Path(".env")


def _ask(prompt: str, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default and not secret else ""
    reader = getpass if secret else input
    value = reader(f"{prompt}{suffix}: ").strip()
    return value or default


def _yes(prompt: str) -> bool:
    return input(f"{prompt} [y/N]: ").strip().lower() in ("y", "yes")


def _save(values: dict[str, str]) -> None:
    ENV_PATH.touch(exist_ok=True)
    os.chmod(ENV_PATH, 0o600)  # only you can read your secrets
    for key, value in values.items():
        if value:
            set_key(str(ENV_PATH), key, value)
            os.environ[key] = value


def run(force: bool = False) -> None:
    """Ask for any missing settings. With force=True, ask for everything again."""
    print("\n=== Messenger Agent setup ===  (press Enter to skip a question)\n")

    if force or not os.environ.get("ANTHROPIC_API_KEY"):
        print("1) Claude API key: create one at https://platform.claude.com (Settings > API keys).")
        _save({"ANTHROPIC_API_KEY": _ask("   Anthropic API key", secret=True)})

    if force or not os.environ.get("SMTP_USERNAME"):
        if _yes("\n2) Set up EMAIL sending now?"):
            print("   Gmail: turn on 2-Step Verification, then create an App Password at")
            print("   https://myaccount.google.com/apppasswords and paste it below.")
            user = _ask("   Your email address")
            host = _ask("   SMTP server", "smtp.gmail.com")
            _save({
                "SMTP_USERNAME": user,
                "SMTP_HOST": host,
                "SMTP_PORT": _ask("   SMTP port", "587"),
                "SMTP_PASSWORD": _ask("   Password / App Password", secret=True),
            })

    if force or not os.environ.get("TWILIO_ACCOUNT_SID"):
        if _yes("\n3) Set up WHATSAPP sending now (needs a free Twilio account)?"):
            print("   In the Twilio Console, copy your Account SID and Auth Token, and open")
            print("   Messaging > Try it out > Send a WhatsApp message to get the sandbox number.")
            _save({
                "TWILIO_ACCOUNT_SID": _ask("   Account SID"),
                "TWILIO_AUTH_TOKEN": _ask("   Auth Token", secret=True),
                "TWILIO_WHATSAPP_FROM": _ask("   WhatsApp sender number", "whatsapp:+14155238886"),
            })

    if not Path("contacts.json").exists() and Path("contacts.example.json").exists():
        shutil.copy("contacts.example.json", "contacts.json")
        print("\nCreated contacts.json from the example: edit it to add your own contacts.")

    print(f"\nSaved to {ENV_PATH.resolve()}. Run with --setup any time to change these.\n")
