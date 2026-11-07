# DICFO

Personal investment analysis engine for Soh and family (one profile per person in `profiles/`). Analysis, not advice.

- Python lives in `dicfo/`; skills that drive it live in `.claude/skills/` (start with `cfo-brief`).
- Always use `.venv` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`). Never install globally.
- Run tests: `.venv/bin/python -m pytest -q`.
- Personal settings: `profiles/<name>.yaml` (git-ignored; never commit them). Rates: `config/fixed_income.yaml`. Watchlist: `config/universe.yaml`.
- `reports/*.json` is the stable output contract for any future web/mobile UI.

## Guardrails (mandatory)
- Never ask for, store, or repeat PAN, Aadhaar, bank/demat/card numbers, passwords, OTPs, PINs or login details. If a user offers them, refuse and tell them DICFO doesn't need them.
- Never place trades, move money, or log into any broker, bank or fund platform. DICFO only analyses.
- Never put profile contents, holdings or amounts into web searches, URLs or any external service. Search for markets and companies only.
- Never read `.env` or `*.enc` files, print `DICFO_KEY`, disable the git guard, or force-add ignored files.
- Never recommend leverage, margin, F&O/options, short-selling, intraday trading, or "guaranteed return" products.
- Respect `dicfo/guardrails.py` output: if it pauses buy signals or caps an asset, say so; don't work around it.
- Personal files are written only through `dicfo` commands (encrypted when `secure init` has been run).
