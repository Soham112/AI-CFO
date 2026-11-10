"""Command line entry point.

  python -m dicfo onboard --name dad          # questionnaire -> profiles/dad.yaml
  python -m dicfo fetch                       # live data -> snapshots/snapshot-DATE.json
  python -m dicfo report --profile dad [--snapshot F] [--overrides F]
  python -m dicfo daily --profile dad --notify telegram,email   # fetch + report + send (for cron)
  python -m dicfo stock GOOGL RELIANCE.NS     # deep dive on tickers (live)
  python -m dicfo fixed-income --profile dad  # EPF/PPF/FD/SCSS/T-bill comparison
  python -m dicfo mf-search "parag parikh"    # find AMFI scheme codes
  python -m dicfo checkin --profile dad       # "did you invest?" for this month's core items
  python -m dicfo log --profile dad RELIANCE.NS 20000   # record any purchase
"""
from __future__ import annotations

import argparse
import json
import os

from . import REPORTS, config
from .data import snapshot as snapmod


def _report(snap, profile_name, as_json=False):
    from .engine import run
    from .report import render, summary
    from . import ledger as led
    profile = config.load_profile(profile_name)
    res = run(snap, profile, led.load(config.profile_path(profile_name).stem))
    REPORTS.mkdir(exist_ok=True)
    tag = f"{str(res['as_of'])[:10]}-{str(profile.get('name', 'me')).lower()}"
    (REPORTS / f"dicfo-{tag}.json").write_text(json.dumps(res, indent=2, default=str))
    md = render(res)
    (REPORTS / f"dicfo-{tag}.md").write_text(md)
    import os
    return res, md, summary(res, redact=os.environ.get("DICFO_PRIVACY", "strict") != "off")


def main(argv=None):
    from .security import SensitiveDataError
    try:
        return _main(argv)
    except (SensitiveDataError, ValueError, RuntimeError) as e:
        raise SystemExit(f"\nDICFO stopped: {e}")


def _main(argv=None):
    config.load_env()
    ap = argparse.ArgumentParser(prog="dicfo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch")
    ob = sub.add_parser("onboard")
    ob.add_argument("--name", required=True)
    for name in ("report", "daily", "fixed-income", "checkin"):
        p = sub.add_parser(name)
        p.add_argument("--profile", help="profiles/<name>.yaml (default: $DICFO_PROFILE or first profile)")
        p.add_argument("--snapshot")
        p.add_argument("--overrides", action="append", default=[],
                       help="JSON merged on top of the snapshot (facts + judgements from a skill)")
        if name == "report":
            p.add_argument("--json", action="store_true")
            p.add_argument("--summary", action="store_true", help="print the short WhatsApp text")
        if name == "daily":
            p.add_argument("--notify", default="", help="comma list: telegram,email,whatsapp")
            p.add_argument("--no-fetch", action="store_true")
    lg = sub.add_parser("log", help="record a purchase")
    lg.add_argument("--profile")
    lg.add_argument("symbol")
    lg.add_argument("amount", type=float)
    lg.add_argument("--date")
    lg.add_argument("--name", default="")
    lg.add_argument("--units", default="")
    lg.add_argument("--price", default="")
    sc = sub.add_parser("secure", help="encryption and permissions")
    sc.add_argument("action", choices=["init", "check", "harden"])
    sp = sub.add_parser("stock")
    sp.add_argument("symbols", nargs="+")
    wl = sub.add_parser("whatsapp-listen", help="answer WhatsApp commands via the whatsapp-mcp bridge")
    wl.add_argument("--profile")
    tl = sub.add_parser("telegram-listen", help="two-way Telegram bot (fixed commands, allowed chats only)")
    tl.add_argument("--profile")
    sub.add_parser("telegram-id", help="find your Telegram chat id after messaging your bot")
    ms = sub.add_parser("mf-search")
    ms.add_argument("query")
    a = ap.parse_args(argv)

    if a.cmd == "secure":
        from . import security
        if a.action == "init":
            return security.init()
        if a.action == "harden":
            print("fixed:", security.harden() or "nothing")
            return
        ok = True
        print("encryption key:", "found" if security.get_key() else "NOT SET (run: python -m dicfo secure init)")
        plain = [p.name for p in config.PROFILES.glob("*") if p.suffix in (".yaml", ".csv")
                 and not p.name.startswith("example-")]
        if plain:
            ok = False
            print("unencrypted personal files:", ", ".join(plain))
        import subprocess
        hp = subprocess.run(["git", "config", "core.hooksPath"], cwd=config.ROOT, capture_output=True, text=True).stdout.strip()
        print("git guard:", "on" if hp == "scripts/hooks" else "OFF")
        ok = ok and hp == "scripts/hooks"
        print("privacy mode:", os.environ.get("DICFO_PRIVACY", "strict"))
        print("OK" if ok else "ACTION NEEDED")
        return

    if a.cmd == "onboard":
        from .onboard import run
        return run(a.name)

    if a.cmd == "log":
        from . import ledger as led
        from .analysis.plan import asset_class
        name = config.profile_path(a.profile).stem
        row = {"symbol": a.symbol, "name": a.name or a.symbol, "amount": a.amount, "units": a.units,
               "price": a.price, "asset_class": asset_class({"symbol": a.symbol, "type": "mf" if a.symbol.isdigit() else "stock"})}
        if a.date:
            row["date"] = a.date
        if not led.validate_row(row):
            raise SystemExit(1)
        led.add(name, [row])
        print(f"recorded {a.symbol} {a.amount:,.0f} in {led.path(name)}")
        return

    if a.cmd == "whatsapp-listen":
        from .whatsapp_listener import serve
        return serve(a.profile)

    if a.cmd == "telegram-listen":
        from .telegram_listener import listen
        return listen(a.profile)

    if a.cmd == "telegram-id":
        from .notify import telegram_chat_id
        print(telegram_chat_id())
        return

    if a.cmd == "mf-search":
        import requests
        r = requests.get("https://api.mfapi.in/mf/search", params={"q": a.query}, timeout=20)
        for row in r.json()[:25]:
            print(row["schemeCode"], row["schemeName"])
        return

    if a.cmd == "fetch" or (a.cmd == "daily" and not a.no_fetch and not a.snapshot):
        from .data.live import collect
        uni = config.load("universe")
        # also fetch NAVs for every fund in every profile
        for pth in config.PROFILES.glob("*.yaml"):
            try:
                for f in (config.load_profile(pth.stem).get("holdings") or {}).get("mutual_funds", []) or []:
                    if f.get("scheme_code"):
                        uni.setdefault("mutual_funds", {})[str(f["scheme_code"])] = f.get("name", "")
            except Exception:
                pass
        snap = collect(uni)
        p = snapmod.save(snap)
        print(f"saved {p}  markets={len(snap['markets'])} fundamentals={len(snap['fundamentals'])} "
              f"news={len(snap['news'])} errors={len(snap['errors'])}")
        if a.cmd == "fetch":
            return

    if a.cmd == "stock":
        from .analysis.fundamentals import analyse_stock
        from .analysis.horizons import stock_views
        from .data.live import fundamentals, prices
        mk, e1 = prices(a.symbols)
        fu, e2 = fundamentals(a.symbols)
        for s in a.symbols:
            if s in mk:
                r = analyse_stock(s, fu.get(s, {}), mk[s], 0.045)
                r["horizons"] = stock_views(r, mk[s])
                print(json.dumps(r, indent=2, default=str))
        for e in e1 + e2:
            print("warn:", e)
        return

    path = a.snapshot or snapmod.latest()
    if not path:
        raise SystemExit("No snapshot. Run `python -m dicfo fetch` or pass --snapshot.")
    snap = snapmod.load(path)
    for o in a.overrides or []:
        snap = snapmod.deep_merge(snap, snapmod.load(o))
    # judgement files written by the cfo-news-policy skill for the same day are picked up automatically
    day = str(snap.get("as_of", ""))[:10]
    if not a.overrides and day:
        for o in sorted(snapmod.SNAPSHOTS.glob(f"overrides-{day}-*.json")):
            snap = snapmod.deep_merge(snap, snapmod.load(o))

    if a.cmd == "fixed-income":
        from .analysis.fixed_income import compare
        print(json.dumps(compare(config.load("fixed_income"), config.load_profile(a.profile),
                                 snap.get("macro", {})), indent=2))
        return

    res, md, short = _report(snap, a.profile)
    if a.cmd == "checkin":
        from . import ledger as led
        return led.checkin(config.profile_path(a.profile).stem, res["monthly_plan"]["pending"])
    if a.cmd == "report":
        print(json.dumps(res, indent=2, default=str) if a.json else short if a.summary else md)
        return
    # daily
    print(short)
    if a.notify:
        from .notify import send
        chans = [c.strip() for c in a.notify.split(",") if c.strip()]
        if "telegram" in chans:      # Telegram gets the simple tap-button cards
            chans.remove("telegram")
            from .telegram_listener import push_daily
            try:
                print(push_daily(res, config.load_profile(a.profile)))
            except Exception as e:
                print("telegram failed:", type(e).__name__)
        for line in send(chans, f"DICFO brief {day} for {res.get('person')}", short, md):
            print(line)


if __name__ == "__main__":
    main()
