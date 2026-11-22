# Messenger Agent

An AI agent, powered by Claude, that writes and sends **emails** and **WhatsApp messages** for you.
You tell it what you want in plain English and it does the rest:

```
You: Tell Alice and Bob the team lunch moved to Friday at 1pm. Email Alice, WhatsApp Bob.
```

The agent looks people up in your contact list, writes each message, shows it to you, and sends it once you say yes.

## How it works

- **Brain:** Claude Opus 5.5, via the Anthropic Python SDK's tool runner (the SDK runs the agent loop).
- **Tools the agent can call:**
  - `find_contact`: searches `contacts.json`
  - `send_email`: sends through any SMTP server (Gmail, Outlook, …)
  - `send_whatsapp`: sends through the Twilio WhatsApp API
- **Safety:** each message is shown to you and only sent if you answer `y`. You can turn this off with `--auto`.
  Your passwords and tokens stay on your machine and are never sent to Claude.
- If Claude's safety filter declines a request, the request is retried on a fallback model automatically (`fallbacks: "default"`).

## Quick start

You need [Python 3.10 or newer](https://www.python.org/downloads/). On Windows, tick **"Add python.exe to PATH"** when installing.

```bash
git clone https://github.com/YoisakiKanade219/My-first-project.git
cd My-first-project
./run.sh          # macOS / Linux
run.bat           # Windows (or double-click it)
```

The first run installs everything into a private `.venv` folder, then asks for your keys and saves them in `.env` on your computer.
To change them later, run `./run.sh --setup`. Every example below works with `./run.sh` (or `run.bat`) in place of `python -m messenger_agent.agent`.

## Manual setup (optional)

If you'd rather not use the launcher:

1. **Install:**
   ```bash
   python -m venv .venv && source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. **Configure:** copy `.env.example` to `.env` and fill it in:
   - `ANTHROPIC_API_KEY`: from https://platform.claude.com
   - **Email (Gmail):** turn on 2-Step Verification, create an
     [App Password](https://myaccount.google.com/apppasswords), and use it as `SMTP_PASSWORD`.
   - **WhatsApp:** create a [Twilio](https://www.twilio.com) account and set up the
     WhatsApp Sandbox (Messaging → Try it out → Send a WhatsApp message). Each recipient
     must first send the sandbox join code to the sandbox number. For real use, register your own WhatsApp sender in Twilio.
3. **Contacts (optional):** copy `contacts.example.json` to `contacts.json` and add your people.
   Phone numbers must be in international format (`+` and country code).

## Usage

```bash
# Interactive chat
python -m messenger_agent.agent

# One-shot
python -m messenger_agent.agent "Email bob@example.com a thank-you note for the gift"

# Try it without sending anything
python -m messenger_agent.agent --dry-run "WhatsApp Alice happy birthday"

# Fully automatic, no confirmation (for scripts and schedules)
python -m messenger_agent.agent --auto "Send Alice the daily standup reminder on WhatsApp"
```

### Sending automatically on a schedule

Use `--auto` with cron (Linux/macOS) or Task Scheduler (Windows). For example, every weekday at 8:45:

```cron
45 8 * * 1-5 cd /path/to/My-first-project && .venv/bin/python -m messenger_agent.agent --auto "WhatsApp the team the standup reminder" >> agent.log 2>&1
```

## Project layout

```
messenger_agent/
  agent.py      # the agent: Claude + tools + chat loop
  channels.py   # SMTP email and Twilio WhatsApp delivery
.env.example    # configuration template
contacts.example.json
```

## Notes

- Only message people who expect to hear from you. WhatsApp and email providers block accounts that send spam.
- Each request uses Claude API tokens (billed to your Anthropic account), and Twilio charges per WhatsApp message.
