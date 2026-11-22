# Messenger Agent

An AI agent that writes and sends **emails** and **WhatsApp messages** for you.
It runs **entirely on your computer** with a free, open AI model, **Qwen 3.5 9B**, through [Ollama](https://ollama.com).
There's no AI subscription and no per-use fee.

```
You: Tell Alice and Bob the team lunch moved to Friday at 1pm. Email Alice, WhatsApp Bob.
```

The agent looks people up in your contact list, writes each message, shows it to you, and sends it once you say yes.

## What you need

- **Python 3.10+**: https://www.python.org/downloads/ (on Windows, tick **"Add python.exe to PATH"**)
- **Ollama**: https://ollama.com/download (free). Install it and leave it running.
- About **7 GB of free disk** and **8 GB+ of RAM** for the model. A graphics card makes it much faster, but isn't required.

## Quick start

```bash
git clone https://github.com/YoisakiKanade219/My-first-project.git
cd My-first-project
./run.sh          # macOS / Linux
run.bat           # Windows (or double-click it)
```

On the first run it will:
1. install the Python packages into a private `.venv` folder,
2. ask whether to set up email and/or WhatsApp, and save your details in `.env` on your computer,
3. download the Qwen 3.5 9B model (about 6.6 GB, one time only).

Run `./run.sh --setup` any time to change your accounts.

## Usage

```bash
./run.sh                                             # chat with it
./run.sh "Email bob@example.com a thank-you note for the gift"
./run.sh --dry-run "WhatsApp Alice happy birthday"   # write it, but don't send
./run.sh --auto "Send Alice the standup reminder on WhatsApp"   # no confirmation (for schedules)
./run.sh --think "..."                               # let the model reason first: slower, more reliable
./run.sh --model qwen3.5:27b "..."                   # use another Ollama model
```

On Windows, use `run.bat` instead of `./run.sh`.

### Sending automatically on a schedule

Use `--auto` with cron (Linux/macOS) or Task Scheduler (Windows). For example, every weekday at 8:45:

```cron
45 8 * * 1-5 cd /path/to/My-first-project && ./run.sh --auto "WhatsApp the team the standup reminder" >> agent.log 2>&1
```

Your computer and Ollama must be on at that time.

## Accounts for sending

- **Email (free):** works with any email account. For Gmail, turn on 2-Step Verification, create an
  [App Password](https://myaccount.google.com/apppasswords), and enter it during setup.
- **WhatsApp (Twilio):** create a [Twilio](https://www.twilio.com) account and open the WhatsApp Sandbox
  (Messaging → Try it out → Send a WhatsApp message). Each recipient must first send the sandbox join code to the sandbox number.
  Testing uses Twilio's trial credit. Messaging real contacts requires your own WhatsApp sender, and **Twilio and Meta charge per message**.
- **Contacts:** edit `contacts.json` (created on first run). Phone numbers need `+` and the country code.

## Costs

| Part | Cost |
|---|---|
| AI model (Qwen 3.5 9B on Ollama) | Free; runs on your own hardware |
| Email | Free with your normal email account |
| WhatsApp via Twilio | Free trial credit for testing; paid per message for real use |

## Tips

- A 9B model is small. It occasionally picks the wrong contact or writes an odd message, so keep the
  "Send this? [y/N]" confirmation on (the default) until you trust it, and try `--think` or a bigger model if results are poor.
- Only message people who expect to hear from you. Email and WhatsApp providers block accounts that send spam.

## Project layout

```
messenger_agent/
  agent.py         # the agent: model + tools + chat loop
  channels.py      # SMTP email and Twilio WhatsApp delivery
  setup_wizard.py  # first-run questions, saved to .env
run.sh / run.bat   # one-command launchers
.env.example       # configuration template
contacts.example.json
```
