# DICFO

Personal investment analysis engine for Soh and family (one profile per person in `profiles/`). Analysis, not advice.

- Python lives in `dicfo/`; skills that drive it live in `.claude/skills/` (start with `cfo-brief`).
- Always use `.venv` (`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt`). Never install globally.
- Run tests: `.venv/bin/python -m pytest -q`.
- Personal settings: `profiles/<name>.yaml` (git-ignored; never commit them). Rates: `config/fixed_income.yaml`. Watchlist: `config/universe.yaml`.
- `reports/*.json` is the stable output contract for any future web/mobile UI.
