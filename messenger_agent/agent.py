"""An AI agent that writes and sends emails and WhatsApp messages for you.

Runs entirely on your computer with a free, open model (Qwen 3.5 9B via Ollama).

Usage:
    python -m messenger_agent.agent                       # interactive chat
    python -m messenger_agent.agent "Email Alice that the meeting moved to 3pm"
    python -m messenger_agent.agent --auto "..."          # send without asking (for scripts / cron)
    python -m messenger_agent.agent --dry-run "..."       # do everything except actually send
    python -m messenger_agent.agent --setup               # set up email / WhatsApp accounts
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

import ollama
from dotenv import load_dotenv

from . import channels, setup_wizard

DEFAULT_MODEL = "qwen3.5:9b"
MAX_STEPS = 15  # safety limit on tool calls per request

SYSTEM_PROMPT = """You are a messaging assistant. You send emails and WhatsApp messages on the user's behalf using your tools.

Rules:
- If the user names a person instead of giving an email address or phone number, call find_contact first. If nobody matches, or several people match, ask the user instead of guessing.
- WhatsApp numbers must be in international format, e.g. +14155550123.
- Write clear, friendly messages. Keep WhatsApp messages short. Give every email a meaningful subject and a greeting and sign-off.
- To send to several people or on several channels, make one tool call per message.
- Only say a message was sent if the tool result says it was sent. If a tool returns an error or the user declined, say so.
- When you are done, reply with a one- or two-line summary of what was sent to whom."""


class Settings:
    auto_send = False
    dry_run = False


def _confirm(preview: str) -> bool:
    """Ask the human before anything leaves the machine (unless --auto or --dry-run)."""
    if Settings.auto_send or Settings.dry_run:
        return True
    print("\n" + "-" * 60 + "\n" + preview + "\n" + "-" * 60)
    try:
        answer = input("Send this? [y/N] ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes")


# --- Tools the model can call. Ollama reads the name, type hints and docstring of each function.

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


def send_whatsapp(to: str, message: str) -> str:
    """Send a WhatsApp message.

    Args:
        to: Recipient phone number in international format, e.g. +14155550123.
        message: The message text.
    """
    if not _confirm(f"WHATSAPP to: {to}\n\n{message}"):
        return "The user declined to send this WhatsApp message. It was not sent."
    try:
        return channels.send_whatsapp(to, message, dry_run=Settings.dry_run)
    except channels.ChannelError as exc:
        return f"Error: {exc}"


def find_contact(query: str) -> str:
    """Look up people in the user's contact list by name, nickname, email or phone number.

    Args:
        query: Part of a name, email, or phone number. Use an empty string to list everyone.
    """
    try:
        contacts = channels.load_contacts()
    except (channels.ChannelError, ValueError) as exc:
        return f"Error reading contacts: {exc}"
    if not contacts:
        return "The contact list is empty. Ask the user for the email address or phone number."
    q = (query or "").strip().lower()
    matches = [c for c in contacts if not q or q in json.dumps(c, ensure_ascii=False).lower()]
    if not matches:
        return f"No contact matches '{query}'."
    return json.dumps(matches, ensure_ascii=False, indent=2)


TOOLS = {f.__name__: f for f in (send_email, send_whatsapp, find_contact)}


def _call_tool(name: str, arguments: dict) -> str:
    tool = TOOLS.get(name)
    if tool is None:
        return f"Error: there is no tool named '{name}'. Available tools: {', '.join(TOOLS)}."
    try:
        return tool(**(arguments or {}))
    except TypeError as exc:  # small models sometimes get the arguments wrong; let them retry
        return f"Error: wrong arguments for {name}: {exc}"


def run_turn(client: ollama.Client, model: str, history: list, think: bool = False) -> None:
    """Let the model work on the latest user message, calling tools until it gives a final answer.

    Everything (model replies and tool results) is appended to `history`.
    """
    for _ in range(MAX_STEPS):
        messages = [{"role": "system", "content": SYSTEM_PROMPT + f"\nToday is {datetime.now():%A %d %B %Y}."}]
        response = client.chat(model=model, messages=messages + history, tools=list(TOOLS.values()), think=think)
        reply = response.message
        history.append(reply)

        if not reply.tool_calls:
            print(f"\nAgent: {(reply.content or '').strip() or '(no reply)'}")
            return

        if reply.content and reply.content.strip():
            print(f"\nAgent: {reply.content.strip()}")
        for call in reply.tool_calls:
            result = _call_tool(call.function.name, dict(call.function.arguments or {}))
            summary = " ".join(result.split())
            print(f"  [{call.function.name}] {summary[:100] + '...' if len(summary) > 100 else summary}")
            history.append({"role": "tool", "tool_name": call.function.name, "content": result})

    print("\n(Stopped: the agent took too many steps. Try rephrasing your request.)")


def ensure_model(client: ollama.Client, model: str) -> bool:
    """Check Ollama is running and the model is downloaded; offer to download it if not."""
    try:
        installed = {m.model for m in client.list().models}
    except ConnectionError:
        print(
            "Can't reach Ollama. Install it from https://ollama.com/download and make sure it's running\n"
            "(open the Ollama app, or run `ollama serve` in another terminal).",
            file=sys.stderr,
        )
        return False
    if model in installed or f"{model}:latest" in installed:
        return True

    print(f"The model '{model}' isn't downloaded yet (about 6.6 GB for qwen3.5:9b, one time only).")
    if sys.stdin.isatty() and input("Download it now? [Y/n] ").strip().lower() in ("n", "no"):
        return False
    last = -1
    for progress in client.pull(model, stream=True):
        if progress.total and progress.completed:
            pct = int(progress.completed * 100 / progress.total)
            if pct != last:
                print(f"\r  {progress.status}: {pct}%   ", end="", flush=True)
                last = pct
    print("\nDownload complete.")
    return True


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="AI agent that sends emails and WhatsApp messages (runs locally).")
    parser.add_argument("instruction", nargs="*", help="What to send. Omit for interactive mode.")
    parser.add_argument("--auto", action="store_true", help="Send without asking for confirmation.")
    parser.add_argument("--dry-run", action="store_true", help="Write messages but don't send anything.")
    parser.add_argument("--setup", action="store_true", help="Set up or change your email / WhatsApp accounts.")
    parser.add_argument("--model", default=os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL),
                        help=f"Ollama model to use (default: {DEFAULT_MODEL}).")
    parser.add_argument("--think", action="store_true",
                        help="Let the model reason before acting: more reliable on tricky requests, but slower.")
    args = parser.parse_args()
    Settings.auto_send = args.auto
    Settings.dry_run = args.dry_run

    if args.setup or (not Path(".env").exists() and sys.stdin.isatty()):
        setup_wizard.run(force=args.setup)

    client = ollama.Client(host=os.environ.get("OLLAMA_HOST", "http://localhost:11434"))
    if not ensure_model(client, args.model):
        return 1

    history: list = []

    def handle(text: str) -> None:
        history.append({"role": "user", "content": text})
        try:
            run_turn(client, args.model, history, think=args.think)
        except ollama.ResponseError as exc:
            print(f"Error from Ollama: {exc.error}", file=sys.stderr)
        except ConnectionError:
            print("Lost connection to Ollama. Is it still running?", file=sys.stderr)

    if args.instruction:
        handle(" ".join(args.instruction))
        return 0

    mode = "DRY RUN" if args.dry_run else ("AUTO-SEND" if args.auto else "confirm before sending")
    print(f"Messenger agent ready, model {args.model} ({mode}). Type what you want to send, or 'quit'.")
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
