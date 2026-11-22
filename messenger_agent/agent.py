"""An AI agent that writes and sends emails and WhatsApp messages for you.

Usage:
    python -m messenger_agent.agent                       # interactive chat
    python -m messenger_agent.agent "Email Alice that the meeting moved to 3pm"
    python -m messenger_agent.agent --auto "..."          # send without asking (for scripts / cron)
    python -m messenger_agent.agent --dry-run "..."       # do everything except actually send
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime

import anthropic
from anthropic import beta_tool
from dotenv import load_dotenv

from . import channels, setup_wizard

MODEL = "claude-opus-5-5"

SYSTEM_PROMPT = """You are a messaging assistant. You send emails and WhatsApp messages on the user's behalf.

How to work:
- If the user names a person rather than an address or number, call find_contact first. If nobody matches, or several people do, ask the user instead of guessing.
- WhatsApp numbers must be in international format (e.g. +14155550123).
- Write messages that are clear and appropriately polite for the recipient. Keep WhatsApp messages short. Give every email a meaningful subject.
- When asked to send to several people or on several channels, send each message with its own tool call.
- If a send fails or the user declines it, say so plainly; never claim a message was sent unless the tool said it was.
- After finishing, give a one- or two-line summary of what was sent to whom."""


class Settings:
    auto_send = False
    dry_run = False


def _confirm(preview: str) -> bool:
    """Ask the human before anything leaves the machine (unless --auto)."""
    if Settings.auto_send or Settings.dry_run:
        return True
    print("\n" + "-" * 60 + "\n" + preview + "\n" + "-" * 60)
    try:
        answer = input("Send this? [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


@beta_tool
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email.

    Args:
        to: Recipient email address.
        subject: Email subject line.
        body: Plain-text email body, including greeting and sign-off.
    """
    if not _confirm(f"EMAIL to: {to}\nSubject: {subject}\n\n{body}"):
        return "The user declined to send this email. It was not sent."
    try:
        return channels.send_email(to, subject, body, dry_run=Settings.dry_run)
    except channels.ChannelError as exc:
        return f"Error: {exc}"


@beta_tool
def send_whatsapp(to: str, message: str) -> str:
    """Send a WhatsApp message.

    Args:
        to: Recipient phone number in international E.164 format, e.g. +14155550123.
        message: The message text.
    """
    if not _confirm(f"WHATSAPP to: {to}\n\n{message}"):
        return "The user declined to send this WhatsApp message. It was not sent."
    try:
        return channels.send_whatsapp(to, message, dry_run=Settings.dry_run)
    except channels.ChannelError as exc:
        return f"Error: {exc}"


@beta_tool
def find_contact(query: str) -> str:
    """Look up people in the user's contact list by name, nickname, email or phone.

    Args:
        query: Part of a name, email, or phone number. Use an empty string to list everyone.
    """
    try:
        contacts = channels.load_contacts()
    except (channels.ChannelError, ValueError) as exc:
        return f"Error reading contacts: {exc}"
    if not contacts:
        return "The contact list is empty. Ask the user for the email address or phone number."
    q = query.strip().lower()
    matches = [c for c in contacts if not q or q in json.dumps(c, ensure_ascii=False).lower()]
    if not matches:
        return f"No contact matches '{query}'."
    return json.dumps(matches, ensure_ascii=False, indent=2)


TOOLS = [send_email, send_whatsapp, find_contact]


def run_turn(client: anthropic.Anthropic, history: list) -> None:
    """Let the agent work on the latest user message until it has nothing left to do.

    Appends every assistant message and tool result to `history`, so the next
    turn of the conversation has the full context.
    """
    runner = client.beta.messages.tool_runner(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM_PROMPT + f"\n\nCurrent date and time: {datetime.now():%A %d %B %Y, %H:%M}.",
        tools=TOOLS,
        messages=list(history),
        output_config={"effort": "medium"},
        # If a safety classifier declines a request, retry it on a fallback model automatically.
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        max_iterations=20,
    )
    for message in runner:
        history.append({"role": "assistant", "content": message.content})
        if message.stop_reason == "refusal":
            print("\nAgent: Sorry, I can't help with that request.")
            return
        for block in message.content:
            if block.type == "text" and block.text.strip():
                print(f"\nAgent: {block.text.strip()}")
        tool_results = runner.generate_tool_call_response()  # runs the tools (cached for the runner)
        if tool_results is not None:
            history.append(tool_results)
    if message.stop_reason == "max_tokens":
        print("\n(The agent's reply was cut off.)")


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="AI agent that sends emails and WhatsApp messages.")
    parser.add_argument("instruction", nargs="*", help="What to send. Omit for interactive mode.")
    parser.add_argument("--auto", action="store_true", help="Send without asking for confirmation.")
    parser.add_argument("--dry-run", action="store_true", help="Write messages but don't send anything.")
    parser.add_argument("--setup", action="store_true", help="Enter or change your API keys and accounts.")
    args = parser.parse_args()
    Settings.auto_send = args.auto
    Settings.dry_run = args.dry_run

    if args.setup or (not os.environ.get("ANTHROPIC_API_KEY") and sys.stdin.isatty()):
        setup_wizard.run(force=args.setup)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("No ANTHROPIC_API_KEY set. Run again with --setup to add it.", file=sys.stderr)
        return 1

    client = anthropic.Anthropic()
    history: list = []

    def handle(text: str) -> None:
        history.append({"role": "user", "content": text})
        try:
            run_turn(client, history)
        except anthropic.AuthenticationError:
            print("Error: invalid or missing ANTHROPIC_API_KEY.", file=sys.stderr)
            raise SystemExit(1)
        except anthropic.RateLimitError:
            print("Error: rate limited by the Claude API; try again shortly.", file=sys.stderr)
        except anthropic.APIStatusError as exc:
            print(f"Error from the Claude API ({exc.status_code}): {exc.message}", file=sys.stderr)
        except anthropic.APIConnectionError:
            print("Error: could not reach the Claude API.", file=sys.stderr)

    if args.instruction:
        handle(" ".join(args.instruction))
        return 0

    mode = "DRY RUN" if args.dry_run else ("AUTO-SEND" if args.auto else "confirm before sending")
    print(f"Messenger agent ready ({mode}). Type what you want to send, or 'quit'.")
    while True:
        try:
            text = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if text.lower() in ("quit", "exit"):
            return 0
        if text:
            handle(text)


if __name__ == "__main__":
    raise SystemExit(main())
