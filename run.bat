@echo off
REM Start the Messenger Agent. First run sets everything up.
REM Usage: run.bat   or   run.bat "Email bob@example.com a thank-you note"   or   run.bat --setup
cd /d "%~dp0"
where python >nul 2>nul || (echo Python 3.10+ is required: https://www.python.org/downloads/ ^(tick "Add python.exe to PATH"^) & pause & exit /b 1)
if not exist .venv (
  echo First run: setting things up, about a minute...
  python -m venv .venv || (pause & exit /b 1)
  .venv\Scripts\python -m pip install --quiet -r requirements.txt || (pause & exit /b 1)
)
.venv\Scripts\python -m messenger_agent.agent %*
if "%~1"=="" pause
