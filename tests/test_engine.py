import numpy as np
import pandas as pd

from dicfo import config
from dicfo.analysis import fixed_income, technicals
from dicfo.analysis.fundamentals import analyse_stock
from dicfo.engine import run
from dicfo.report import render


def series(drop=0.12, n=800):
    up = np.linspace(100, 150, n - 40)
    down = np.linspace(150, 150 * (1 - drop), 40)
    return pd.Series(np.concatenate([up, down]))


def test_metrics_and_dip():
    m = technicals.metrics(series(0.12))
    assert abs(m["off_high_52w"] + 0.12) < 0.01
    assert technicals.dip_score(m) >= 1.0
    near_high = technicals.metrics(series(0.0))
    assert technicals.dip_score(near_high) < 0


def test_quality_stock_on_dip_is_accumulate():
    m = technicals.metrics(series(0.15))
    f = {"roe": 0.30, "op_margin": 0.32, "debt_to_equity": 0.1, "revenue_growth": 0.14,
         "fcf": 7e10, "forward_pe": 19, "peg": 1.1, "analyst_target": m["price"] * 1.3, "eps": 10, "bvps": 30}
    r = analyse_stock("TEST", f, m, 0.045)
    assert r["action"].startswith("ACCUMULATE")
    assert r["lenses"]["buffett"]["passed"] == "4/4"


def test_pfic_and_ppf_eligibility():
    p = config.load_profile("example-india-resident") | {"residency": "US", "tax_residency": "US",
        "tax": {"us_federal_marginal": 0.24, "us_state_marginal": 0.05, "india_slab": 0.3}, "spend_currency": "USD"}
    rows = {r["key"]: r for r in fixed_income.compare(config.load("fixed_income"), p,
                                                    {"us_cpi_yoy": 0.03, "fed_funds": 0.04})}
    assert rows["ppf"]["eligible_new_money"] is False      # NRI in US
    assert rows["nre_fd"]["eligible_new_money"] is True
    # INR return in USD terms is reduced by rupee depreciation
    assert rows["nre_fd"]["in_spend_currency"] < rows["nre_fd"]["after_tax"]


def test_engine_end_to_end():
    snap = {"as_of": "2026-01-01", "source": "test",
            "markets": {"^GSPC": technicals.metrics(series(0.12)), "^NSEI": technicals.metrics(series(0.02))},
            "macro": {"us_cpi_yoy": 0.037, "fed_funds": 0.04, "us10y": 0.048, "brent": 98, "us_vix": 24},
            "news": [{"title": "Trump threatens new tariff on India"}],
            "drivers": {"gold": {"test": {"score": 0.5, "why": "unit test"}}}}
    r = run(snap, config.load_profile("example-india-resident") | {"residency": "US", "tax_residency": "US"})
    assert abs(sum(r["allocation"]["tactical"].values()) - 100) < 0.5
    assert r["asset_scores"]["us_equity"]["score"] > r["asset_scores"]["india_equity"]["score"]
    assert "trade_policy" in r["news_signals"]
    assert any(f["id"] == "pfic" for f in r["tax_flags"])
    assert "DICFO brief" in render(r)


def test_banks_not_penalised_for_leverage():
    m = technicals.metrics(series(0.05))
    r = analyse_stock("BANK", {"is_bank": True, "roe": 0.17, "op_margin": 0.35, "forward_pe": 14}, m, 0.065)
    assert r["quality"] >= 8


FIX = __import__("pathlib").Path(__file__).parent / "fixtures"


def test_india_resident_dad():
    from dicfo.data import snapshot as sm
    snap = sm.deep_merge(sm.load(FIX / "snapshot-2026-11-06.json"), sm.load(FIX / "overrides-2026-11-06-judgement.json"))
    dad = config.load_profile("example-india-resident")
    r = run(snap, dad)
    assert r["currency"] == "INR"
    assert r["allocation"]["strategic"]["india_equity"] > r["allocation"]["strategic"]["us_equity"]
    fi = {f["key"]: f for f in r["fixed_income"]}
    assert fi["ppf"]["eligible_new_money"] and not fi["nre_fd"]["eligible_new_money"]
    assert not fi["scss"]["eligible_new_money"]            # age 55 < 60
    assert not any(t["id"] == "pfic" for t in r["tax_flags"])
    assert r["portfolio_review"]["total_value"] > 0
    assert set(r["horizon_views"]["gold"]) >= {"short", "medium", "long"}
    from dicfo.report import render, summary
    assert len(summary(r)) <= 3000 and "Rs" in render(r)


def test_review_challenges_bad_portfolio():
    from dicfo.analysis.portfolio import review
    p = {"monthly_income": 0, "employment": "job_searching", "emergency_fund_have_months": 2,
         "holdings": {"mutual_funds": [
             {"name": f"Fund {i} Regular Growth", "category": "flexi_cap", "value": 1000, "plan": "regular"}
             for i in range(7)] + [{"name": "XYZ Defence Fund", "category": "sectoral_thematic", "value": 500}]}}
    titles = " ".join(i["title"] for i in review(p, {}, {"india_equity": 100})["issues"])
    assert "No income" in titles and "too many" in titles and "Regular plan" in titles and "Thematic" in titles


def test_notify_skips_without_secrets(monkeypatch):
    from dicfo import notify
    for k in ("DICFO_SMTP_HOST", "TELEGRAM_BOT_TOKEN", "TWILIO_ACCOUNT_SID"):
        monkeypatch.delenv(k, raising=False)
    out = notify.send(["email", "telegram", "whatsapp"], "s", "t", "m")
    assert all("skipped" in o for o in out)


def test_core_and_opportunistic_plan_and_ledger(tmp_path, monkeypatch):
    import datetime as dt
    from dicfo import ledger as led
    from dicfo.analysis.plan import review
    monkeypatch.setattr(led, "PROFILES", tmp_path)
    prof = {"plan": {"core": [{"symbol": "120716", "type": "mf", "name": "Nifty", "monthly": 10000}],
                     "opportunistic": [{"symbol": "X.NS", "budget": 30000, "buy_below_pct": -10, "tranches": 3}]}}
    snap = {"markets": {"X.NS": {"price": 80, "off_high_52w": -0.2}}}
    r = review(prof, snap, [], dt.date(2026, 11, 7))
    assert r["pending"][0]["pending"] == 10000
    assert r["opportunistic"][0]["status"] == "BUY" and "10,000" in r["opportunistic"][0]["message"]
    led.add("t", [{"date": "2026-11-05", "symbol": "120716", "amount": 10000, "asset_class": "india_equity"}])
    r = review(prof, snap, led.load("t"), dt.date(2026, 11, 7))
    assert r["pending"] == []


def test_sensitive_data_is_refused():
    import pytest
    from dicfo.security import SensitiveDataError, assert_clean
    for bad in ({"pan": "x"}, {"note": "PAN ABCDE1234F"}, {"note": "aadhaar 2345 6789 0123"},
                {"note": "card 4111 1111 1111 1111"}, {"bank_password": "x"}, {"note": "123-45-6789"}):
        with pytest.raises(SensitiveDataError):
            assert_clean(bad, "test")
    assert_clean({"name": "Dad", "scheme_code": "122639", "value": 500000}, "ok")


def test_encryption_roundtrip(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    from dicfo import security
    monkeypatch.setenv("DICFO_KEY", Fernet.generate_key().decode())
    p = tmp_path / "dad.yaml"
    security.write_private(p, b"name: Dad\n")
    assert not p.exists() and (tmp_path / "dad.yaml.enc").exists()
    assert b"Dad" not in (tmp_path / "dad.yaml.enc").read_bytes()
    assert security.read_private(p) == b"name: Dad\n"
    import os, stat
    assert stat.S_IMODE(os.stat(tmp_path / "dad.yaml.enc").st_mode) == 0o600


def test_guardrails():
    import pytest
    from dicfo.guardrails import validate_profile
    with pytest.raises(ValueError):
        validate_profile({"age": 5})
    snap = {"as_of": "2020-01-01", "markets": {"^GSPC": technicals.metrics(series(0.3))}, "macro": {}}
    jobless = config.load_profile("example-india-resident") | {"monthly_income": 0, "employment": "job_searching"}
    r = run(snap, jobless)
    assert r["monthly_split"] == {} and not r["data_ok"]
    assert r["allocation"]["tactical"]["crypto"] <= 3 and r["allocation"]["tactical"]["gold"] <= 15
    assert abs(sum(r["allocation"]["tactical"].values()) - 100) < 0.5
    ef_short = config.load_profile("example-india-resident") | {"emergency_fund_have_months": 2}
    assert list(run(snap, ef_short)["monthly_split"]) == ["us_cash_bonds"]


def test_whatsapp_summary_has_no_amounts():
    import re
    from dicfo.data import snapshot as sm
    from dicfo.report import summary
    snap = sm.load(FIX / "snapshot-2026-11-06.json")
    r = run(snap, config.load_profile("example-india-resident"), max_data_age_days=10_000)
    s = summary(r, redact=True)
    assert not re.search(r"Rs ?[\d,]{4,}", s)
    assert re.search(r"Rs ?[\d,]{4,}", summary(r, redact=False))


def test_ledger_typo_guard():
    from dicfo.ledger import validate_row
    assert not validate_row({"amount": "-5"})
    assert not validate_row({"amount": "5000", "date": "2999-01-01"})
    assert not validate_row({"amount": 900000}, planned=5000, confirm=lambda _: "no")
    assert validate_row({"amount": 900000}, planned=5000, confirm=lambda _: "YES")


def test_summary_never_cuts_mid_line():
    from dicfo.data import snapshot as sm
    from dicfo.report import summary
    r = run(sm.load(FIX / "snapshot-2026-11-06.json"), config.load_profile("example-india-resident"))
    s = summary(r, limit=400)
    assert len(s) <= 400 and s.endswith("Analysis, not advice.") and "(more on the laptop)" in s


def test_whatsapp_listener_rules(monkeypatch, tmp_path):
    from dicfo import whatsapp_listener as wl
    b = wl.Brain("example-india-resident", {"19455440767"})
    msg = lambda text, sender="19455440767@s.whatsapp.net", i=None: wl.extract(
        {"id": i or text, "sender": sender, "chat_jid": sender, "content": text})
    assert b.handle(msg("help", sender="15550001111@s.whatsapp.net")) is None      # stranger ignored
    assert b.handle(msg("hey how are you")) is None                                # chat ignored
    assert b.handle(msg(wl.TAG + " help")) is None                                 # own echo ignored
    assert "commands" in b.handle(msg("help"))
    assert b.handle(msg("help", i="help")) is None                                 # duplicate id ignored
    assert "ID or account" in b.handle(msg("invested 5000 PAN ABCDE1234F", i="x1"))
    monkeypatch.setattr(b, "_result", lambda: ({"monthly_plan": {"month": "2026-11", "core": [
        {"symbol": "120716", "name": "UTI Nifty 50 Index Fund", "monthly": 10000, "asset_class": "india_equity",
         "verdict": "CONTINUE", "pending": 10000}], "opportunistic": []}}, "t"))
    from dicfo import ledger
    monkeypatch.setattr(ledger, "PROFILES", tmp_path)
    assert "recorded UTI Nifty" in b.handle(msg("invested 10,000 UTI Nifty", i="x2"))
    assert "unusual" in b.handle(msg("invested 900000 UTI Nifty", i="x3"))
    assert "couldn't match" in b.handle(msg("invested 100 dogecoin", i="x4"))
    assert len(ledger.load("t")) == 1


def test_whatsapp_listener_http_auth():
    import threading, urllib.request, urllib.error
    from http.server import ThreadingHTTPServer
    from dicfo import whatsapp_listener as wl
    srv = ThreadingHTTPServer(("127.0.0.1", 0), wl.make_handler(wl.Brain(None, {"1"}), "secret"))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/whatsapp/webhook"
    def post(tok):
        req = urllib.request.Request(url, data=b'{"content":"hi"}', headers={"X-Bridge-Token": tok}, method="POST")
        try:
            return urllib.request.urlopen(req).status
        except urllib.error.HTTPError as e:
            return e.code
    assert post("wrong") == 401 and post("secret") == 200
    srv.shutdown()


def test_telegram_update_parsing_and_allowlist():
    from dicfo.telegram_listener import to_message
    from dicfo.whatsapp_listener import Brain
    b = Brain(None, {"111"})
    mine = to_message({"update_id": 1, "message": {"chat": {"id": 111}, "text": "help", "date": 0}})
    other = to_message({"update_id": 2, "message": {"chat": {"id": 222}, "text": "help", "date": 0}})
    assert "commands" in b.handle(mine) and b.handle(other) is None


def test_env_example_has_no_real_secrets():
    from dicfo.config import leaked_example_secrets
    assert leaked_example_secrets() == [], "a secret was typed into .env.example; move it to .env"


def _dad_result():
    from dicfo.data import snapshot as sm
    snap = sm.load(FIX / "snapshot-2026-11-06.json")
    snap["markets"]["TCS.NS"]["off_high_52w"] = -0.16      # make one opportunistic BUY fire
    return run(snap, config.load_profile("example-india-resident"), [], max_data_age_days=10_000)


def test_simple_message_plain_english():
    import datetime as dt
    from dicfo import friendly
    r = _dad_result()
    prof = config.load_profile("example-india-resident")
    msg = friendly.simple_message(r, prof, today=dt.date(2026, 11, 10))
    assert "TCS is 16% cheaper than its best price this year" in msg and "₹20,000" in msg
    for jargon in ("52-week", "tranche", "regime", "overweight", "underweight", "bullish", "bearish", "see the laptop"):
        assert jargon not in msg.lower(), jargon
    assert "done UTI Nifty" in msg
    month = friendly.simple_month(r, prof)
    assert "November 2026" in month and "not done yet" in month


def test_bot_text_replies(monkeypatch, tmp_path):
    from dicfo import ledger
    from dicfo.telegram_listener import Bot
    monkeypatch.setattr(ledger, "PROFILES", tmp_path)
    r = _dad_result()
    bot = Bot("example-india-resident", {"111"})
    monkeypatch.setattr(bot, "_result", lambda: (r, "t"))
    bot.on_text("999", "today")
    assert bot.out == []                                          # stranger: nothing
    bot.on_text("111", "hi")
    assert "reply with" in bot.out[-1][1]["text"] and bot.out[-1][1]["buttons"] == []
    bot.on_text("111", "today")
    assert "Good morning" in bot.out[-1][1]["text"]
    bot.on_text("111", "done UTI Nifty")
    assert "Saved" in bot.out[-1][1]["text"] and ledger.load("t")[0]["amount"] == "10000"
    bot.on_text("111", "done banana")
    assert "couldn't find" in bot.out[-1][1]["text"]
    bot.on_text("111", "my pan is ABCDE1234F")
    assert "ID or account" in bot.out[-1][1]["text"]
    assert all(c["buttons"] == [] for _, c in bot.out)


def test_chat_onboarding_creates_profile(monkeypatch, tmp_path):
    from dicfo import config as cfg
    from dicfo.telegram_listener import Bot
    monkeypatch.setattr(cfg, "PROFILES", tmp_path)
    import dicfo.security as sec
    monkeypatch.delenv("DICFO_KEY", raising=False)
    monkeypatch.setattr(sec, "get_key", lambda: None)
    bot = Bot("newdad", {"111"})
    bot.on_text("111", "hi")                                     # no profile -> setup starts
    assert "set up" in bot.out[0][1]["text"]
    for v in ["Ramesh", "58", "1", "150000", "40000", "3", "3", "2", "1",
              "Parag Parikh Flexi Cap 500000 SIP 10000", "done", "1200000", "0",
              "HDFC Bank 50 at 1450", "TCS 10", "Relaince 5", "banana", "done", "1"]:
        bot.on_text("111", v)
    assert (tmp_path / "newdad.yaml").exists(), [c["text"] for _, c in bot.out[-3:]]
    p = cfg.load_profile("newdad")
    assert p["language"] == "en" and p["employment"] == "salaried" and p["plan"]["core"][0]["monthly"] == 10000
    assert [x["symbol"] for x in p["holdings"]["stocks"]] == ["HDFCBANK.NS", "TCS.NS"]
    assert p["holdings"]["stocks"][0]["shares"] == 50 and p["invest_abroad"] == "no"
    assert p["holdings"]["stocks"][0]["avg_price"] == 1450 and p["holdings"]["stocks"][1]["avg_price"] is None


def test_name_to_symbol():
    from dicfo.names import to_symbol
    assert to_symbol("Infosys Ltd") == ("INFY.NS", True)
    assert to_symbol("hdfcbank", ["HDFCBANK.NS"]) == ("HDFCBANK.NS", True)
    assert to_symbol("IRCTC") == ("IRCTC.NS", False)
    assert to_symbol("some small company") == (None, False)
    from dicfo.names import resolve
    assert resolve("IRCTC", [], {"IRCTC.NS"}) == ("IRCTC.NS", "")
    sym, msg = resolve("Relaince", ["RELIANCE.NS"])
    assert sym is None and "Reliance" in msg


def test_owned_shares_and_india_only():
    from dicfo.data import snapshot as sm
    from dicfo.friendly import simple_month
    snap = sm.deep_merge(sm.load(FIX / "snapshot-2026-11-06.json"), sm.load(FIX / "overrides-2026-11-06-judgement.json"))
    india_profile = config.load_profile("example-india-resident")
    p = dict(india_profile, invest_abroad="no")
    p["holdings"] = dict(p["holdings"], stocks=[{"name": "TCS", "symbol": "TCS.NS", "shares": 2000},
                                                {"name": "Mystery", "symbol": None, "shares": 5}])
    r = run(snap, p)
    assert r["allocation"]["tactical"]["us_equity"] == 0
    held = r["portfolio_review"]["holdings_check"]
    assert held[0]["value"] and held[0]["view"] != "unknown" and held[1]["view"] == "unknown"
    assert r["portfolio_review"]["current_mix"]["india_equity"] > india_profile["holdings"]["other"].get("india_equity", 0)
    assert "Shares you own" in simple_month(r, p)


def test_bot_understands_bought_shares(monkeypatch, tmp_path):
    from dicfo import config as cfg, ledger
    from dicfo.data import snapshot as sm
    from dicfo.telegram_listener import Bot, parse_bought
    import dicfo.security as sec
    assert parse_bought("I have bought 10 shares of tcs shares") == (10, "tcs")
    assert parse_bought("bought 10 TCS") == (10, "TCS")
    assert parse_bought("Bought HDFC Bank 50") == (50, "HDFC Bank")
    assert parse_bought("hello") == (0, "")
    monkeypatch.setattr(cfg, "PROFILES", tmp_path)
    monkeypatch.setattr(ledger, "PROFILES", tmp_path)
    monkeypatch.delenv("DICFO_KEY", raising=False)
    monkeypatch.setattr(sec, "get_key", lambda: None)
    (tmp_path / "t.yaml").write_text((cfg.ROOT / "profiles" / "example-india-resident.yaml").read_text())
    snap = sm.deep_merge(sm.load(FIX / "snapshot-2026-11-06.json"), sm.load(FIX / "overrides-2026-11-06-judgement.json"))
    bot = Bot("t", {"111"})
    monkeypatch.setattr(bot.brain, "_result", lambda: (run(snap, cfg.load_profile("t"), ledger.load("t")), "t"))
    bot.on_text("111", "I have bought 10 shares of tcs shares")
    assert "Saved" in bot.out[-1][1]["text"] and "TCS" in bot.out[-1][1]["text"]
    row = ledger.load("t")[-1]
    assert row["symbol"] == "TCS.NS" and row["units"] == "10"
    r = run(snap, cfg.load_profile("t"), ledger.load("t"))
    assert any(h["symbol"] == "TCS.NS" and h["shares"] == 10 for h in r["portfolio_review"]["holdings_check"])
    bot.on_text("111", "invested 20000 in Infosys")
    assert "Saved" in bot.out[-1][1]["text"] and ledger.load("t")[-1]["symbol"] == "INFY.NS"
    bot.on_text("111", "bought 10 TCS at 2000")
    assert "at ₹2,000 each" in bot.out[-1][1]["text"] or "Saved" in bot.out[-1][1]["text"]
    bot.on_text("111", "profit")
    assert "TCS" in bot.out[-1][1]["text"] and "simple profit" in bot.out[-1][1]["text"]
    bot.on_text("111", "sold 10 shares of TCS")
    bot.on_text("111", "sold 4 shares of TCS")
    assert "sold 4" in bot.out[-1][1]["text"]
    bot.on_text("111", "sold 50 TCS")
    assert "didn't record" in bot.out[-1][1]["text"]
    r = run(snap, cfg.load_profile("t"), ledger.load("t"))
    assert any(h["symbol"] == "TCS.NS" and h["shares"] == 6 for h in r["portfolio_review"]["holdings_check"])
    n = len(ledger.load("t"))
    bot.on_text("111", "bought 10 shares of TSC")             # typo: must not be saved
    assert "didn't save" in bot.out[-1][1]["text"] and "TCS" in bot.out[-1][1]["text"]
    assert len(ledger.load("t")) == n
    p = cfg.load_profile("t")
    p["holdings"]["stocks"] = [{"name": "Hadf bank", "symbol": None, "shares": 5}]
    from dicfo.chat_onboard import save
    save("t", p)
    bot.on_text("111", "remove Hadf bank")
    assert "Removed" in bot.out[-1][1]["text"] and cfg.load_profile("t")["holdings"]["stocks"] == []
    bot.on_text("111", "holdings")
    assert "Shares:" in bot.out[-1][1]["text"] and "TCS" in bot.out[-1][1]["text"]
    bot.on_text("111", "remove Parag Parikh Flexi Cap Fund - Direct Growth")
    assert "funds" in bot.out[-1][1]["text"]
    bot.on_text("111", "HDFC Mid Cap 200000 invested 150000 SIP 5000")
    assert "Added HDFC Mid Cap" in bot.out[-1][1]["text"]
    pf = cfg.load_profile("t")
    assert any(f["name"] == "HDFC Mid Cap" and f["invested"] == 150000 for f in pf["holdings"]["mutual_funds"])
    assert any(c["name"] == "HDFC Mid Cap" and c["monthly"] == 5000 for c in pf["plan"]["core"])
    bot.on_text("111", "/setup")
    assert "replaces everything" in bot.out[-2][1]["text"]
    bot.on_text("111", "cancel")
    assert "Nothing was changed" in bot.out[-1][1]["text"] and ledger.load("t")
    bot.on_text("111", "I bought something nice")
    assert "bought 10 shares of TCS" in bot.out[-1][1]["text"]


def _xlsx(rows):
    import io, openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    b = io.BytesIO()
    wb.save(b)
    return b.getvalue()


def test_holdings_file_import(monkeypatch, tmp_path):
    from dicfo import config as cfg, ledger
    from dicfo.holdings_import import parse, to_profile_parts
    from dicfo.telegram_listener import Bot
    import dicfo.security as sec
    zerodha = _xlsx([["Client ID", "AB1234"], [], ["Symbol", "ISIN", "Sector", "Quantity Available", "Quantity Long Term",
                     "Average Price", "Previous Closing Price"],
                     ["HDFCBANK", "INE040A01034", "Banks", 50, 50, 1450.5, 1600],
                     ["TCS", "INE467B01029", "IT", 10, 0, 3100, 3300]])
    groww_csv = ("Stock Name,ISIN,Quantity,Average buy price,Buy value,Closing price,Closing value\n"
                 "HDFC BANK LTD,INE040A01034,50,1450,72500,1600,80000\n"
                 "SOME SMALL CO LTD,INE000000000,7,100,700,120,840\n").encode()
    groww_mf = ("Scheme Name,AMC,Category,Folio No.,Units,Invested Value,Current Value\n"
                "Parag Parikh Flexi Cap Fund Direct Growth,PPFAS,Equity,12345678,1000.5,380000,500000\n").encode()
    z = to_profile_parts(parse(zerodha, "holdings.xlsx"), ["HDFCBANK.NS", "TCS.NS"], set())
    assert [(s["symbol"], s["shares"], s["avg_price"]) for s in z["stocks"]] == [("HDFCBANK.NS", 50, 1450.5), ("TCS.NS", 10, 3100)]
    coin = _xlsx([["Symbol", "ISIN", "Quantity Available", "Average Price"],
                  ["PARAG PARIKH FLEXI CAP FUND - DIRECT PLAN", "INF879O01027", 1000.5, 80]])
    cz = to_profile_parts(parse(coin, "mf.xlsx"), [], set())
    assert not cz["stocks"] and cz["funds"][0]["invested"] == 80040
    g = to_profile_parts(parse(groww_csv, "h.csv"), ["HDFCBANK.NS"], set())
    assert g["stocks"][0]["symbol"] == "HDFCBANK.NS" and g["stocks"][1]["symbol"] is None and g["stocks"][1]["value"] == 840
    f = to_profile_parts(parse(groww_mf, "mf.csv"), [], set())["funds"][0]
    assert f["invested"] == 380000 and f["value"] == 500000 and "12345678" not in str(f)
    try:
        parse(b"%PDF-1.4 ...", "x.pdf")
        assert False
    except ValueError as e:
        assert "PDF" in str(e)
    # through the bot: preview, then yes
    monkeypatch.setattr(cfg, "PROFILES", tmp_path)
    monkeypatch.setattr(ledger, "PROFILES", tmp_path)
    monkeypatch.delenv("DICFO_KEY", raising=False)
    monkeypatch.setattr(sec, "get_key", lambda: None)
    (tmp_path / "t.yaml").write_text((cfg.ROOT / "profiles" / "example-india-resident.yaml").read_text())
    bot = Bot("t", {"111"})
    bot.on_document("111", "holdings.xlsx", zerodha)
    assert "Reply yes" in bot.out[-1][1]["text"] and "2 shares" in bot.out[-1][1]["text"]
    assert "AB1234" not in bot.out[-1][1]["text"]
    bot.on_text("111", "yes")
    assert "Saved" in bot.out[-1][1]["text"]
    st = cfg.load_profile("t")["holdings"]["stocks"]
    assert len(st) == 2 and "AB1234" not in str(cfg.load_profile("t"))


def test_setup_accepts_many_lines():
    from dicfo.chat_onboard import Onboarding, QUESTIONS
    ob = Onboarding()
    ob.i = [q[0] for q in QUESTIONS].index("stocks")
    ob.answer("TCS 10 at 3100\nHDFC Bank 50 at 1450\nINFY 5")
    assert [s["symbol"] for s in ob.stocks] == ["TCS.NS", "HDFCBANK.NS", "INFY.NS"]
