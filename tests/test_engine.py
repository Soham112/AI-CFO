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
