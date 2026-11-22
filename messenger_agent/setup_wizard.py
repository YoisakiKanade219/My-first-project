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
    ENV_PATH.touch(exist_ok=True)  # so setup only runs automatically the first time
    os.chmod(ENV_PATH, 0o600)

    if force or not os.environ.get("SMTP_USERNAME"):
        if _yes("1) Set up EMAIL sending now?"):
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

    if force or not os.environ.get("WHATSAPP_TOKEN"):
        if _yes("\n2) Set up WHATSAPP sending now (free Meta developer account)?"):
            print("   At https://developers.facebook.com create an app of type 'Business' and add WhatsApp.")
            print("   Open WhatsApp > API Setup: copy the access token and the 'Phone number ID'.")
            print("   (The temporary token lasts 24 hours; see the README for a permanent one.)")
            _save({
                "WHATSAPP_TOKEN": _ask("   Access token", secret=True),
                "WHATSAPP_PHONE_NUMBER_ID": _ask("   Phone number ID"),
            })

    if not Path("contacts.json").exists() and Path("contacts.example.json").exists():
        shutil.copy("contacts.example.json", "contacts.json")
        print("\nCreated contacts.json from the example: edit it to add your own contacts.")

    print(f"\nSaved to {ENV_PATH.resolve()}. Run with --setup any time to change these.\n")
