# Installing DICFO on a laptop (e.g. Dad's)

Everything runs on the laptop. No server, no cloud deploy. Personal data stays in `profiles/` and
`.env`, which are never pushed to GitHub.

## 1. One-time setup (about 15 minutes)

**Windows**
1. Install Python 3.11+ from python.org (tick "Add Python to PATH") and Git from git-scm.com.
2. Open PowerShell:
   ```powershell
   cd $HOME\Documents
   git clone https://github.com/<your-username>/DICFO.git
   cd DICFO
   python -m venv .venv
   .\.venv\Scripts\pip install -r requirements.txt
   ```

**macOS / Linux**
```bash
git clone https://github.com/<your-username>/DICFO.git && cd DICFO
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
```
(Packages go only into `.venv`, never system-wide.)

## 2. Tell it about the person
```bash
.venv/bin/python -m dicfo onboard --name dad        # Windows: .\.venv\Scripts\python -m dicfo onboard --name dad
```
It asks age, income, monthly investing amount, each mutual fund (find codes with
`python -m dicfo mf-search "fund name"`), EPF/PPF/FD, gold, stocks. Edit `profiles/dad.yaml` any time.

## 2b. Lock it down (do this once)
```bash
.venv/bin/python -m dicfo secure init     # encrypts profiles/ledgers, key goes in the OS keychain
.venv/bin/python -m dicfo secure check    # should end with OK
```
Back up the key (Windows: Credential Manager → "dicfo"; Mac: Keychain Access → "dicfo") in a
password manager. See [SECURITY.md](../SECURITY.md) for everything that's protected.

## 3. Try it
```bash
.venv/bin/python -m dicfo fetch
.venv/bin/python -m dicfo report --profile dad            # full brief, saved in reports/
.venv/bin/python -m dicfo report --profile dad --summary  # the short WhatsApp version
```

## 4. Daily messages
Copy `.env.example` to `.env` and fill in one or both:

- **Email (Gmail):** turn on 2-Step Verification, create an App Password (Google Account → Security →
  App passwords), put it in `DICFO_SMTP_PASS`.
- **Telegram (recommended, free, official):** in Telegram search **@BotFather**, send `/newbot`,
  pick a name, copy the token into `TELEGRAM_BOT_TOKEN`. Open your new bot, press **Start**, then
  run `python -m dicfo telegram-id` and paste the printed `TELEGRAM_CHAT_ID` into `.env`.
- **WhatsApp (Twilio, paid):** Twilio is an official Meta provider. Create an account, join the
  WhatsApp sandbox from your phone, fill the `TWILIO_*` values. WhatsApp only delivers free-form
  messages within 24 hours of your last message to that number, so daily briefs can fail on quiet
  days unless a template is approved. CallMeBot-style unofficial relays are deliberately not supported.

Test: `.venv/bin/python -m dicfo daily --profile dad --notify telegram,email`

**Schedule it**
- Windows: Task Scheduler → Create Basic Task → Daily 8:30 AM → Start a program:
  `powershell.exe` with arguments `-ExecutionPolicy Bypass -File "C:\Users\<you>\Documents\DICFO\scripts\daily.ps1" -Profile dad`.
  Tick "Run whether user is logged on or not" and "Wake the computer to run this task".
- macOS/Linux: `crontab -e`, add `30 8 * * 1-5 /path/to/DICFO/scripts/daily.sh dad >> /path/to/DICFO/daily.log 2>&1`

The laptop has to be on (or asleep with wake enabled) at that time.

## 5. Each month: "Did you invest?"
The daily message lists core investments not yet recorded this month. After investing, run
`python -m dicfo checkin --profile dad` and answer y / n / amount for each. Other purchases:
`python -m dicfo log --profile dad RELIANCE.NS 20000`. Everything goes into
`profiles/dad-ledger.csv` (open it in Excel any time). Replying on WhatsApp itself isn't supported
yet: that needs an always-on server, which we're avoiding for now.

## 6. Smarter briefs with Claude Code (optional)
The scheduled job uses data plus keyword news rules. For real judgement on news, policy, Trump/RBI
decisions and company events, open the folder in Claude Code and say
"run the CFO brief for dad". That uses the skills in `.claude/skills/`. Set `DICFO_USE_CLAUDE=1`
to let the Mac/Linux daily script call Claude Code headlessly first.

## Updating
`git pull` in the folder. Your `profiles/` and `.env` are untouched.
