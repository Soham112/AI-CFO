# Security and guardrails

DICFO holds a family's financial picture, so it's built to keep that on the laptop and to keep
the advice safe even when the model is wrong.

## What protects the data
| Risk | Protection |
|---|---|
| Laptop file theft / other users | `python -m dicfo secure init` encrypts profiles and ledgers (AES via Fernet). The key lives in the OS keychain (Windows Credential Manager / macOS Keychain). Personal files are owner-only (chmod 600/700). |
| Storing things that enable fraud | The tool **refuses** to save PAN, Aadhaar, card/account numbers, IFSC, SSN, passwords, PINs, OTPs, demat/login IDs. It never needs them. |
| Leaking to GitHub | `.gitignore` excludes profiles, ledgers, `.env`, reports, snapshots. A git pre-commit guard blocks those files and ID-like numbers even if someone forces them. |
| Leaking through messages | Only official APIs are used (Telegram Bot API, Twilio for WhatsApp, your own email); unofficial relays such as CallMeBot are not supported. Messages still pass through those providers, so by default (`DICFO_PRIVACY=strict`) messages contain **no amounts or holdings**, only market views and to-dos. The full brief is attached to email only if `DICFO_EMAIL_FULL=1`. |
| Secrets in code | Email/WhatsApp credentials live only in `.env` (git-ignored, owner-only). Errors never print them. All sending is over verified TLS. |
| AI assistant overreach | `.claude/settings.json` stops Claude Code from reading `.env`/encrypted files, force-adding, disabling the guard, or curling arbitrary URLs. `CLAUDE.md` forbids asking for IDs, trading, or putting personal data in searches. |

Also recommended: turn on BitLocker (Windows) or FileVault (Mac), use a login password, and keep a backup of the encryption key (export it from the keychain) in a password manager. Lose the key and the encrypted files can't be recovered.

## What keeps the advice safe (`dicfo/guardrails.py`)
- Never: leverage, margin, F&O/options, short-selling, intraday, "guaranteed return" schemes.
- No income or emergency fund short → no new risky investments; new money fills the emergency fund first.
- Caps: crypto ≤3%, silver ≤5%, gold ≤15%, any single stock ≤5% of the portfolio.
- Equity ceiling by age and horizon (e.g. ≤30% if money is needed within 3 years).
- Stale (>3 days) or suspicious data (index moving >20% in a day) → buy signals and top-ups paused; regular SIPs continue.
- Ledger typo guard: negative, future-dated, or unusually large entries are rejected or need typing YES.
- Every output says it's analysis, not advice.

## Checking
`python -m dicfo secure check` reports whether encryption, the git guard and privacy mode are on.
