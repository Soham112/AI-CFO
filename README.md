# DICFO (backend)

A personal CFO that runs on your own laptop: one install, several people (each has a profile), a daily brief by email or WhatsApp.

A personal investment-analysis engine that answers "where is the opportunity right now?"
across US & Indian equities, gold, silver, other emerging markets, crypto, EPF/PPF/FDs and US cash,
after tax and inflation, for a US-resident investor with ties to India.

> Analysis, not financial advice. Every recommendation shows the data and the judgement behind it.

## How it works

```
 Claude Code skills (.claude/skills)         Python engine (dicfo/)                 Output
 ─────────────────────────────────           ───────────────────────                ──────
 cfo-brief  (orchestrates)  ─────────►  fetch: Yahoo, FRED, AMFI, News RSS ─┐
 cfo-market-data (fallback via web) ──►  snapshot JSON  ◄── overrides JSON ─┤
 cfo-news-policy (judgement) ─────────►  drivers {asset: {name: score, why}} │
 cfo-commodities, cfo-stock-deep-dive    engine.run():                       ├─► reports/cfo-DATE.json  (app contract)
 cfo-tax-allocation                        technicals → dip score            │   reports/cfo-DATE.md    (brief)
                                           fundamentals → quality/value/lenses
                                           macro rules + news + judgement → asset scores
                                           allocation: strategic ± tilt, dip ladder
                                           fixed income: after-tax, after-FX, real
                                           tax flags (PFIC, NRI, FBAR, shelters)
```

**Skills vs agents.** Skills are the right core: each one is a repeatable playbook (how to read
news, how to analyse a stock, cross-border tax rules) that Claude loads only when needed. But
skills shouldn't do arithmetic or fetch prices from memory, so the numbers live in tested Python
that the skills call. Separate agents are only worth it for parallel research (e.g. ten news
topics at once); everything else is a skill.

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # never install globally
.venv/bin/python -m dicfo onboard --name dad    # questionnaire → profiles/dad.yaml
.venv/bin/python -m dicfo fetch                 # live data → snapshots/
.venv/bin/python -m dicfo report --profile dad  # brief → reports/
.venv/bin/python -m dicfo daily --profile dad --notify email,whatsapp
.venv/bin/python -m dicfo stock GOOGL RELIANCE.NS
.venv/bin/python -m dicfo fixed-income
.venv/bin/python -m pytest -q
```

Or in Claude Code, in this folder: *"run the CFO brief"* (triggers the `cfo-brief` skill).

Full laptop setup, daily scheduling, email and WhatsApp: see [docs/INSTALL.md](docs/INSTALL.md).

## What it covers
- **Assets:** US & Indian equities (S&P 500 top 30, all Nifty 50 stocks), mid/small-cap ETFs, gold, silver, other EM, crypto, Indian MFs (any AMFI code), EPF/PPF/FD/SCSS/RBI bonds, US T-bills.
- **Horizons:** every asset and stock gets a short (1-3 months), medium (3-12 months) and long (3+ years) view.
  Short-term views only time the buying; DICFO never recommends trading, short-selling or F&O.
- **Portfolio challenge:** too many funds, overlapping categories, Regular plans, sector funds, underperformance vs a Nifty index fund, missing emergency fund, SIPs with no income, allocation gaps.
- **Tax:** India-resident and US-resident rules (PFIC, NRI, FBAR, LTCG, new/old regime, LRS/TCS).

## Configure
- `profiles/<name>.yaml`: one per person (git-ignored). Start from `profiles/example-india-resident.yaml` or run `onboard`.
- `config/universe.yaml`: watchlist, ETFs, Indian MF scheme codes, news queries.
- `config/fixed_income.yaml`: EPF/PPF/FD/T-bill rates (verify quarterly).

## Better data (optional)
Free sources are enough to start. Claude connectors for FactSet, Morningstar, Financial Modeling Prep,
Alpha Vantage or Financial Datasets add analyst estimates and cleaner fundamentals. Anthropic's
open-source financial-services plugins (github.com/anthropics/financial-services) include an
earnings-reviewer and market-researcher you can install alongside these skills.
