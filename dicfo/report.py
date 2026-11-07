"""Render an engine result as a readable Markdown CFO brief."""
from __future__ import annotations

LABEL = {"us_equity": "US equity", "india_equity": "India equity", "emerging_equity": "Other EM equity",
         "gold": "Gold", "silver": "Silver", "crypto": "Crypto", "india_fixed_income": "India EPF/PPF/FD",
         "us_cash_bonds": "Cash / T-bills / liquid funds"}


def pct(x, d=1):
    return "n/a" if x is None else f"{x * 100:+.{d}f}%"


def pp(x, d=1):
    return "n/a" if x is None else f"{x * 100:.{d}f}%"


def num(x, d=2):
    return "n/a" if x is None else f"{x:,.{d}f}"


def stance(score):
    return ("Strong overweight" if score >= 1.25 else "Overweight" if score >= 0.4 else
            "Neutral" if score > -0.4 else "Underweight" if score > -1.25 else "Strong underweight")


def summary(r: dict, limit: int = 3000, redact: bool = True) -> str:
    """Short plain-text version for WhatsApp / email.

    redact=True (default) leaves out every amount and holding value, because the
    message passes through third parties (WhatsApp relay, email provider).
    """
    cur = "Rs " if r.get("currency") == "INR" else "$"
    m = r["macro"]
    lines = [f"DICFO {str(r['as_of'])[:10]} for {r.get('person', 'you')}",
             f"Regime: {r['regime'].replace('_', ' ')}"]
    mk = {k: v for k, v in [("S&P", r["asset_scores"]["us_equity"]["proxy_metrics"]),
                             ("Nifty", r["asset_scores"]["india_equity"]["proxy_metrics"]),
                             ("Gold", r["asset_scores"]["gold"]["proxy_metrics"])] if v}
    for k, v in mk.items():
        lines.append(f"{k} {v.get('price', 0):,.0f} ({pct(v.get('chg_1d'))} today, {pct(v.get('off_high_52w'))} from high)")
    if m.get("brent"):
        lines.append(f"Brent ${m['brent']:.0f} | USD/INR {m.get('usdinr', 0):.2f}")
    lines.append("")
    lines.append("Stance (short/medium):")
    for a, s in sorted(r["asset_scores"].items(), key=lambda x: -x[1]["score"]):
        if not r["allocation"]["tactical"][a]:
            continue
        v = r["horizon_views"][a]
        lines.append(f"- {LABEL[a]}: {stance(s['score'])} ({v['short']}/{v['medium']}) -> {r['allocation']['tactical'][a]}%")
    heads = [h["headlines"][0] for h in r.get("news_signals", {}).values() if h.get("headlines")][:3]
    if heads:
        lines.append("")
        lines.append("News driving this:")
        lines += [f"- {h}" for h in heads]
    top = [s for s in r["stocks"] if s["action"].startswith("ACCUMULATE")][:3]
    if top:
        lines.append("")
        lines.append("Accumulate on dips: " + ", ".join(f"{s['name']} ({s['symbol']})" for s in top))
    hi = [i for i in (r.get("portfolio_review") or {}).get("issues", []) if i["severity"] == "high"]
    if hi:
        lines.append("")
        lines.append("Action needed: " + "; ".join(i["title"] for i in hi[:2]))
    mp = r.get("monthly_plan") or {}
    buys = [o for o in mp.get("opportunistic", []) if o["status"] == "BUY"]
    tops = [c for c in mp.get("core", []) if c["verdict"] != "CONTINUE"]
    if buys or tops:
        lines.append("")
        lines.append("Today:")
        for o in buys:
            msg = o["message"].split(" Buy one tranche")[0] + " Amount: see the laptop." if redact else o["message"]
            lines.append(f"- BUY {o['name']}: {msg}")
        for c in tops:
            lines.append(f"- {c['verdict']} {c['name']}: {c['why']}")
    if mp.get("pending"):
        lines.append("")
        lines.append("Did you invest this month? Not recorded yet: " +
                     ", ".join(c["name"] if redact else f"{c['name']} {cur}{c['pending']:,.0f}" for c in mp["pending"]))
        lines.append("Record it: run `python -m dicfo checkin` on the laptop.")
    if not r.get("data_ok", True):
        lines.append("")
        lines.append("Data check failed today: buy signals paused.")
    if r["monthly_split"] and not mp.get("core") and not redact:
        lines.append("")
        lines.append("This month: " + ", ".join(f"{LABEL[a]} {cur}{v:,}" for a, v in
                                                 sorted(r["monthly_split"].items(), key=lambda x: -x[1]) if v))
    lines.append("")
    lines.append("Analysis, not advice.")
    text = "\n".join(lines)
    if len(text) <= limit:
        return text
    # Too long: drop the news block first, then trim whole lines (never cut mid-word).
    if "News driving this:" in lines:
        i = lines.index("News driving this:")
        j = i + 1
        while j < len(lines) and lines[j].startswith("- "):
            j += 1
        lines = lines[:i - 1] + lines[j:]
    tail = ["", "Analysis, not advice."]
    body = lines[:-2]
    while body and len("\n".join(body + ["(more on the laptop)"] + tail)) > limit:
        body.pop()
    return "\n".join(body + ["(more on the laptop)"] + tail)


def render(r: dict) -> str:
    L = []
    w = L.append
    w(f"# DICFO brief for {r.get('person', 'you')}: {str(r['as_of'])[:10]}")
    w(f"_Data: {r['data_source']}. Market regime: **{r['regime'].replace('_', ' ')}**._\n")
    for n in r.get("notes", []):
        w(f"> {n}")
    w("")
    if r.get("guardrails"):
        w("## Guardrails applied")
        for g in r["guardrails"]:
            w(f"- 🛡️ {g}")
        w("")
    m = r["macro"]
    w("## Macro dashboard")
    w("| Indicator | Value |\n|---|---|")
    rows = [("US CPI y/y", pp(m.get("us_cpi_yoy"))), ("Fed funds", pp(m.get("fed_funds"), 2)),
            ("US 10y", pp(m.get("us10y"), 2)), ("US VIX", num(m.get("us_vix"), 1)),
            ("India CPI y/y", pp(m.get("india_cpi_yoy"))), ("RBI repo", pp(m.get("india_repo"), 2)),
            ("USD/INR", num(m.get("usdinr"))), ("Brent $/bbl", num(m.get("brent"), 1)),
            ("Gold $/oz", num(m.get("gold_usd"), 0)), ("Silver $/oz", num(m.get("silver_usd"), 2))]
    for k, v in rows:
        if v != "n/a":
            w(f"| {k} | {v} |")
    w("")
    w("## Asset-class scorecard and target allocation")
    w("| Asset | Stance | Score | Off 52w high | Trend | Strategic | Tactical now |")
    w("|---|---|---|---|---|---|---|")
    from .analysis.technicals import trend
    for a, s in r["asset_scores"].items():
        pm = s["proxy_metrics"]
        w(f"| {LABEL[a]} | {stance(s['score'])} | {s['score']:+.2f} | {pct(pm.get('off_high_52w'))} | "
          f"{trend(pm) if pm else '-'} | {r['allocation']['strategic'][a]}% | **{r['allocation']['tactical'][a]}%** |")
    w("\n**Why (drivers per asset):**")
    for a, s in r["asset_scores"].items():
        if s["drivers"]:
            parts = ", ".join(f"{k} {v:+.2f}" for k, v in s["drivers"].items())
            w(f"- {LABEL[a]}: dip {s['dip']:+.2f}; {parts}")
    for a, j in r.get("judgements", {}).items():
        for k, v in j.items():
            if isinstance(v, dict) and v.get("why"):
                w(f"  - _{LABEL.get(a, a)} / {k}: {v['why']}_")
    w("")
    cur = "Rs " if r.get("currency") == "INR" else "$"
    w("## Short, medium and long-term view")
    w("Short = 1-3 months (only used to time buys), medium = 3-12 months, long = 3+ years.")
    w("| Asset | Short | Medium | Long |\n|---|---|---|---|")
    for a, v in r["horizon_views"].items():
        w(f"| {LABEL[a]} | {v['short']} | {v['medium']} | {v['long']} |")
    w("")
    mp = r.get("monthly_plan") or {}
    if mp.get("core") or mp.get("opportunistic"):
        w(f"## Monthly plan ({mp['month']})")
        if mp.get("core"):
            w("**Core: bought every month, whatever the market does.**")
            w("| Item | Monthly | Verdict | Why | Recorded this month |\n|---|---|---|---|---|")
            for c in mp["core"]:
                w(f"| {c['name']} | {cur}{c['monthly']:,.0f} | {c['verdict']} | {c['why']} | {cur}{c['done_this_month']:,.0f} |")
        if mp.get("opportunistic"):
            w("\n**Opportunistic: bought only when the price falls to a set level.**")
            w("| Item | Status | Detail | Budget left |\n|---|---|---|---|")
            for o in mp["opportunistic"]:
                w(f"| {o['name']} | {o['status']} | {o['message']} | {cur}{o['budget_left']:,.0f} |")
        for x in mp.get("warnings", []):
            w(f"- ⚠️ {x}")
        if mp.get("reserve_monthly"):
            w(f"\nPark {cur}{mp['reserve_monthly']:,.0f} a month in a liquid fund as dry powder for opportunistic buys.")
        w("")
    if r["monthly_split"]:
        w(f"## Where this month's {cur}{sum(r['monthly_split'].values()):,} goes")
        w("| Asset | Amount | How to hold it |\n|---|---|---|")
        for a, amt in sorted(r["monthly_split"].items(), key=lambda x: -x[1]):
            if amt:
                w(f"| {LABEL[a]} | {cur}{amt:,} | {r['vehicles'][a]} |")
        w("")
    pr = r.get("portfolio_review") or {}
    if pr.get("issues") or pr.get("total_value"):
        w(f"## Your portfolio, challenged")
        if pr.get("total_value"):
            w(f"Total tracked: {cur}{pr['total_value']:,.0f}; monthly SIPs: {cur}{pr['sip_total']:,.0f}.")
            w("| Asset | Now | Target | Gap |\n|---|---|---|---|")
            for a, g in pr["gaps"].items():
                w(f"| {LABEL[a]} | {g['current_pct']}% | {g['target_pct']}% | {'+' if g['gap_value'] >= 0 else ''}{cur}{g['gap_value']:,} |")
        for i in pr.get("issues", []):
            icon = {"high": "🔴", "medium": "🟠", "low": "🔵"}[i["severity"]]
            w(f"- {icon} **{i['title']}.** {i['detail']}")
        w("")
    w("## Staged buy-the-dip plan for lump sums")
    w("Do not go all-in on one day. Deploy spare cash in tranches as the index falls from its 52-week high:")
    for name, plan in r["dip_plans"].items():
        if plan:
            steps = "; ".join(f"{p['deploy_pct']}% at {pct(p['trigger_drawdown'], 0)} ({num(p['index_level'], 0)}) "
                              f"{'✅' if p['status'] == 'triggered' else '⏳'}" for p in plan)
            w(f"- **{name}**: {steps}")
    w("")
    if r["stocks"]:
        w("## Company watchlist (quality 0-10, value -3..+3, dip -1..+2)")
        w("| Stock | Price | Off high | Fwd P/E | ROE | Quality | Value | Dip | Short / Medium / Long | Action | Lenses passed |")
        w("|---|---|---|---|---|---|---|---|---|---|---|")
        for s in r["stocks"]:
            lp = " ".join(f"{k.split('_')[0].title()} {v['passed']}" for k, v in s["lenses"].items())
            w(f"| {s['name']} ({s['symbol']}) | {num(s['price'])} | {pct(s['off_high_52w'])} | "
              f"{num(s['forward_pe'], 1)} | {pp(s['roe'], 0)} | {s['quality']:.0f} | {s['value']:+.0f} | "
              f"{s['dip']:+.2f} | {s['horizons']['short']} / {s['horizons']['medium']} / {s['horizons']['long']} | {s['action']} | {lp} |")
        w("")
    w("## Guaranteed / low-risk options, compared honestly")
    w("Return after tax, converted to the currency you spend, minus inflation:")
    w("| Instrument | Nominal | Tax | After tax | In spend ccy | Real | Can add new money? |")
    w("|---|---|---|---|---|---|---|")
    for f in r["fixed_income"]:
        w(f"| {f['name']} | {pp(f['nominal'], 2)} | {pp(f['tax_rate'], 0)} | {pp(f['after_tax'], 2)} | "
          f"{pp(f['in_spend_currency'], 2)} | {pct(f['real'], 2)} | {'yes' if f['eligible_new_money'] else 'no'} |")
    w("")
    w("## Tax flags for you")
    for t in r["tax_flags"]:
        icon = {"high": "🔴", "medium": "🟠", "info": "🔵"}[t["severity"]]
        w(f"- {icon} **{t['title']}.** {t['detail']}")
    w("")
    if r["news_signals"]:
        w("## News signals picked up")
        for k, h in r["news_signals"].items():
            w(f"- **{k}** ({h['count']} headlines): " + " | ".join(h["headlines"]))
        w("")
    if r["data_errors"]:
        w("<details><summary>Data gaps</summary>\n")
        for e in r["data_errors"][:30]:
            w(f"- {e}")
        w("\n</details>\n")
    w(f"---\n_{r['disclaimer']}_")
    return "\n".join(L)
