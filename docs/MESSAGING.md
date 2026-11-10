# Messaging: daily brief + two-way commands

| Option | Cost | Official? | Two-way | Sees other chats? | Recommended |
|---|---|---|---|---|---|
| **Telegram bot** | free | yes | yes, instant (long polling, no server) | no | ✅ |
| Email | free | yes | no | no | backup |
| WhatsApp via Twilio | ~1¢/msg | yes (Meta partner) | needs public webhook | no | if it must be WhatsApp |
| WhatsApp via whatsapp-mcp bridge | free | **no** (linked device) | yes, instant | **yes, copies all chats** | only with a spare number |

## Telegram (recommended)
1. In Telegram, message **@BotFather** → `/newbot` → copy the token into `.env` as `TELEGRAM_BOT_TOKEN=`.
2. Open your new bot and press **Start**. Run `python -m dicfo telegram-id` and put the printed
   `TELEGRAM_CHAT_ID=` line in `.env` (comma-separate several people; the first gets the daily brief).
3. Daily brief: `python -m dicfo daily --profile dad --notify telegram`.
4. Two-way: `python -m dicfo telegram-listen --profile dad`. One plain-English message arrives each
   morning (what the markets did, what to do today, which SIPs aren't marked paid yet). Replies:
   - `today` (today's message again) · `month` (this month's plan) · `help`
   - `done UTI Nifty` marks this month's SIP as paid
   - `invested 20000 TCS` notes any other purchase
   - `/setup` answers about 13 simple questions (reply with numbers) to create the profile, no terminal needed
   - Optional: `TELEGRAM_DETAIL_CHAT_ID=<your chat>` also sends you (Soh) the detailed version.
5. Keep it running at login: `scripts/autostart/` has a macOS LaunchAgent and a Windows script.

## Safety rules (both listeners)
- Only allow-listed chats/numbers get answers; everyone else is silently ignored.
- Only the four fixed commands run. No shell, no free-form AI, no file access.
- Messages containing ID/account-number patterns are refused.
- Telegram cards show suggested buy amounts but never totals or holdings (`DICFO_SHOW_AMOUNTS=0` hides amounts too); 20 commands/hour limit; duplicates and old backlog ignored.
- Unusual amounts can't be recorded from chat; they must be confirmed on the laptop.

## WhatsApp via whatsapp-mcp (optional, unofficial)
[verygoodplugins/whatsapp-mcp](https://github.com/verygoodplugins/whatsapp-mcp) links the laptop as a WhatsApp
"Linked Device". Risks: against WhatsApp's terms (the number can be banned), and it stores **all**
chats unencrypted in `whatsapp-bridge/store/` (use FileVault/BitLocker). Use a spare number.
1. Install Go and uv, clone the repo, run the bridge, scan the QR code from the phone.
2. Bridge env: `WEBHOOK_URL=http://127.0.0.1:8769/whatsapp/webhook` (set it explicitly so requests are signed).
3. DICFO `.env`: `DICFO_WA_ALLOWED=<your number>`, `DICFO_WA_BRIDGE_TOKEN=<whatsapp-bridge/store/.bridge-token>`,
   `DICFO_WA_DAILY_TO=<number or chat JID>`.
4. `python -m dicfo whatsapp-listen --profile dad`; daily: `--notify whatsapp-bridge`.
