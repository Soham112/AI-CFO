---
name: cfo-news-policy
description: Read market, policy and company news (Trump/US policy, Fed, India government/RBI, exports and tariffs, oil, AI capex, Google, Reliance) and turn it into scored driver judgements for the DICFO engine.
---

# News and policy judgement

The engine already tags headlines with keyword rules (`dicfo/analysis/macro.py:NEWS_RULES`).
Your job is the judgement a keyword can't make.

## 1. Gather (last 3-7 days)
Read `snapshot.news`, then web-search each of these and open the 1-2 best primary sources:
- **US policy:** Trump tariffs/executive orders, sector-specific actions (chips, pharma, H-1B,
  remittance tax), Fed decisions and hike/cut odds, midterm/Congress outcomes.
- **India policy:** RBI MPC, GST/budget moves, PLI schemes, FPI/FII flows, SEBI rules.
- **Trade/exports:** US-India trade deal, tariffs on Indian goods (textiles, gems, pharma, IT services).
- **Oil & geopolitics:** OPEC+, Iran/Strait of Hormuz, Russia sanctions. India imports ~85% of crude.
- **AI cycle:** hyperscaler capex, chip export rules, AI regulation, earnings of NVDA/GOOGL/MSFT.
- **Company catalysts:** Google (search share, cloud, antitrust remedies, Gemini), Reliance
  (Jio IPO, retail, new energy, refining margins), any stock in the watchlist.
- **Gold:** central-bank buying, ETF flows, real yields, Indian festive/wedding demand.

## 2. Score
For each asset class (`us_equity, india_equity, emerging_equity, gold, silver, crypto,
india_fixed_income, us_cash_bonds`) give 0-3 drivers, each scored -1.0..+1.0 for the next
3-12 months. Weigh: is it already priced in? Is it reversible (a tweet vs a law)? Who is
directly hit (exporters vs domestic consumption)?

Write `snapshots/overrides-<date>-judgement.json`:
```json
{"drivers": {
  "india_equity": {"fii_return": {"score": 0.5, "why": "FIIs bought Rs15k cr on Nov 5, largest in 6y (source)"}},
  "us_equity": {"ai_capex_doubt": {"score": -0.5, "why": "..."}}
}}
```
Every `why` must name the fact and its source. Keep total judgement per asset within ±1.5 so
data still matters.

## 3. Sanity check
- Don't double-count a theme the keyword rules already caught (check `news_signals` in the report).
- Say what would flip each judgement.
