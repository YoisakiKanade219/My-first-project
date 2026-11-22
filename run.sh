#!/usr/bin/env bash
# Start the Messenger Agent. First run creates a virtual environment and installs everything.
# Usage: ./run.sh            (chat)
#        ./run.sh "Email bob@example.com a thank-you note"
#        ./run.sh --setup    (change keys)
set -e
cd "$(dirname "$0")"

PY=$(command -v python3 || command -v python || true)
if [ -z "$PY" ]; then
  echo "Python 3.10+ is required. Install it from https://www.python.org/downloads/" >&2
  exit 1
fi

if [ ! -d .venv ]; then
  echo "First run: setting things up (about a minute)..."
  "$PY" -m venv .venv
  .venv/bin/python -m pip install --quiet --upgrade pip
fi
if [ ! -f .venv/.installed ] || [ requirements.txt -nt .venv/.installed ]; then
  .venv/bin/python -m pip install --quiet -r requirements.txt
  touch .venv/.installed
fi

exec .venv/bin/python -m messenger_agent.agent "$@"
