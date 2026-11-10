"""Plain-language Telegram cards for non-technical users ("Dad mode").

Each card is {"text": html, "buttons": [[(label, callback_data), ...], ...]}.
Rules: only message when there is something to do; plain words (buy / hold / wait);
suggested buy amounts are shown, portfolio totals and holdings never are.
"""
from __future__ import annotations

import datetime as dt
import html
import os

T = {
    "en": {
        "hello": "Good morning{name} ☀️",
        "nothing": "Nothing to do today. Your plan is on track 👍",
        "mood_calm": "Markets are calm.",
        "mood_shaky": "Markets are shaky. Don't panic: stick to the plan.",
        "mood_falling": "Markets have fallen a lot. This is usually when patient buying pays off. Stick to the plan.",
        "buy_title": "🟢 Good time to buy {name}",
        "buy_body": "It is {dd}% cheaper than its highest price this year.\nYour plan: buy {amt} now (part 1 of {n}).",
        "topup_title": "➕ Extra top-up idea: {name}",
        "topup_body": "It is {dd}% below its high and the business is still strong. If you have spare cash, add one extra instalment of {amt}.",
        "review_title": "⚠️ Check {name}",
        "review_body": "The business looks weaker than before. Pause new money into it until we review it together.",
        "checkin": "📅 Did your {amt} for {name} go in this month?",
        "b_bought": "✅ I bought it", "b_skip": "⏭ Skip", "b_why": "📖 Why?",
        "b_yes": "✅ Yes", "b_no": "❌ No", "b_other": "✏️ Other amount",
        "recorded": "✅ Saved: {amt} in {name}. Thank you!",
        "skipped": "OK, skipped {name}.",
        "noted_no": "OK, noted that {name} didn't go in. Try to catch up when you can.",
        "ask_amount": "How much did you put into {name}? Just type the number, e.g. 10000",
        "bad_amount": "That amount looks unusual. Please check and type it again, or ask Soh.",
        "why_head": "Why {name}?",
        "menu": "What would you like?",
        "m_today": "📊 Today", "m_month": "📅 This month", "m_help": "❓ Help",
        "help": ("I'm your Personal CFO 🤖\n• I message you when there's something to do.\n"
                 "• Tap the buttons to tell me what you did.\n• Tap 📖 Why? for the reason.\n"
                 "Never send PAN, Aadhaar, bank numbers or passwords here."),
        "month_head": "📅 Your plan for {month}",
        "done": "done ✅", "pending": "not yet",
        "disclaimer": "This is analysis, not a guarantee.",
    },
    "hi": {
        "hello": "सुप्रभात{name} ☀️",
        "nothing": "आज कुछ करने की ज़रूरत नहीं है। आपका प्लान सही चल रहा है 👍",
        "mood_calm": "बाज़ार शांत है।",
        "mood_shaky": "बाज़ार में उतार-चढ़ाव है। घबराएँ नहीं, प्लान पर टिके रहें।",
        "mood_falling": "बाज़ार काफ़ी गिरा है। धैर्य से खरीदने का यही समय होता है। प्लान पर टिके रहें।",
        "buy_title": "🟢 {name} खरीदने का अच्छा समय",
        "buy_body": "यह इस साल की सबसे ऊँची कीमत से {dd}% सस्ता है।\nआपका प्लान: अभी {amt} खरीदें ({n} में से पहला हिस्सा)।",
        "topup_title": "➕ अतिरिक्त निवेश का मौका: {name}",
        "topup_body": "यह अपनी ऊँचाई से {dd}% नीचे है और कंपनी अभी भी मज़बूत है। अगर पैसे बचे हों तो {amt} की एक अतिरिक्त किस्त डालें।",
        "review_title": "⚠️ {name} जाँचें",
        "review_body": "कंपनी पहले से कमज़ोर दिख रही है। जब तक हम साथ में न देख लें, इसमें नया पैसा न डालें।",
        "checkin": "📅 क्या इस महीने {name} में {amt} गया?",
        "b_bought": "✅ खरीद लिया", "b_skip": "⏭ छोड़ें", "b_why": "📖 क्यों?",
        "b_yes": "✅ हाँ", "b_no": "❌ नहीं", "b_other": "✏️ दूसरी रकम",
        "recorded": "✅ सेव हो गया: {name} में {amt}। धन्यवाद!",
        "skipped": "ठीक है, {name} छोड़ दिया।",
        "noted_no": "ठीक है, नोट कर लिया कि {name} में पैसा नहीं गया।",
        "ask_amount": "{name} में कितना डाला? सिर्फ़ संख्या लिखें, जैसे 10000",
        "bad_amount": "यह रकम असामान्य लग रही है। कृपया जाँच कर फिर से लिखें, या सोहम से पूछें।",
        "why_head": "{name} क्यों?",
        "menu": "आप क्या देखना चाहेंगे?",
        "m_today": "📊 आज", "m_month": "📅 इस महीने", "m_help": "❓ मदद",
        "help": ("मैं आपका पर्सनल CFO हूँ 🤖\n• जब कुछ करना होगा, मैं मैसेज करूँगा।\n"
                 "• आपने क्या किया, बटन दबाकर बताएँ।\n• कारण जानने के लिए 📖 क्यों? दबाएँ।\n"
                 "यहाँ कभी PAN, आधार, बैंक नंबर या पासवर्ड न भेजें।"),
        "month_head": "📅 {month} का आपका प्लान",
        "done": "हो गया ✅", "pending": "अभी नहीं",
        "disclaimer": "यह विश्लेषण है, गारंटी नहीं।",
    },
    "mr": {
        "hello": "सुप्रभात{name} ☀️",
        "nothing": "आज काही करायची गरज नाही. तुमचा प्लॅन व्यवस्थित चालू आहे 👍",
        "mood_calm": "बाजार शांत आहे.",
        "mood_shaky": "बाजारात चढ-उतार आहेत. घाबरू नका, प्लॅनप्रमाणे चला.",
        "mood_falling": "बाजार बराच खाली आला आहे. संयमाने खरेदी करण्याची हीच वेळ असते. प्लॅनप्रमाणे चला.",
        "buy_title": "🟢 {name} खरेदी करण्याची चांगली वेळ",
        "buy_body": "हा या वर्षीच्या सर्वोच्च किमतीपेक्षा {dd}% स्वस्त आहे.\nतुमचा प्लॅन: आता {amt} खरेदी करा ({n} पैकी पहिला भाग).",
        "topup_title": "➕ अतिरिक्त गुंतवणुकीची संधी: {name}",
        "topup_body": "हा उच्चांकापेक्षा {dd}% खाली आहे आणि कंपनी अजूनही मजबूत आहे. पैसे शिल्लक असतील तर {amt} चा एक अतिरिक्त हप्ता टाका.",
        "review_title": "⚠️ {name} तपासा",
        "review_body": "कंपनी आधीपेक्षा कमकुवत दिसते. आपण एकत्र पाहीपर्यंत यात नवीन पैसे टाकू नका.",
        "checkin": "📅 या महिन्यात {name} मध्ये {amt} गेले का?",
        "b_bought": "✅ खरेदी केले", "b_skip": "⏭ सोडा", "b_why": "📖 का?",
        "b_yes": "✅ हो", "b_no": "❌ नाही", "b_other": "✏️ वेगळी रक्कम",
        "recorded": "✅ सेव्ह झाले: {name} मध्ये {amt}. धन्यवाद!",
        "skipped": "ठीक आहे, {name} सोडले.",
        "noted_no": "ठीक आहे, {name} मध्ये पैसे गेले नाहीत अशी नोंद केली.",
        "ask_amount": "{name} मध्ये किती टाकले? फक्त आकडा लिहा, उदा. 10000",
        "bad_amount": "ही रक्कम असामान्य वाटते. कृपया तपासून पुन्हा लिहा, किंवा सोहमला विचारा.",
        "why_head": "{name} का?",
        "menu": "तुम्हाला काय पाहायचे आहे?",
        "m_today": "📊 आज", "m_month": "📅 हा महिना", "m_help": "❓ मदत",
        "help": ("मी तुमचा पर्सनल CFO आहे 🤖\n• काही करायचे असेल तेव्हा मी मेसेज करीन.\n"
                 "• तुम्ही काय केले ते बटण दाबून सांगा.\n• कारणासाठी 📖 का? दाबा.\n"
                 "इथे कधीही PAN, आधार, बँक नंबर किंवा पासवर्ड पाठवू नका."),
        "month_head": "📅 {month} चा तुमचा प्लॅन",
        "done": "झाले ✅", "pending": "अजून नाही",
        "disclaimer": "हे विश्लेषण आहे, हमी नाही.",
    },
}


def t(lang: str, key: str, **kw) -> str:
    s = T.get(lang, T["en"]).get(key) or T["en"][key]
    return s.format(**{k: html.escape(str(v), quote=False) for k, v in kw.items()})


def money(x: float, cur: str) -> str:
    sym = "₹" if cur == "INR" else "$"
    if cur == "INR":
        n = f"{x:,.0f}"
        # Indian grouping: 1,23,45,678
        s = str(int(round(x)))
        if len(s) > 3:
            head, tail = s[:-3], s[-3:]
            parts = []
            while len(head) > 2:
                parts.insert(0, head[-2:])
                head = head[:-2]
            n = ",".join([head] + parts if head else parts) + "," + tail
        return f"{sym}{n}"
    return f"{sym}{x:,.0f}"


def show_amounts() -> bool:
    return os.environ.get("DICFO_SHOW_AMOUNTS", "1") != "0"


def _amt(x, cur):
    return money(x, cur) if show_amounts() else "the planned amount"


def _mood(r) -> str:
    return {"calm_bull": "mood_calm", "pullback_volatile": "mood_shaky", "correction": "mood_shaky",
            "bear_market": "mood_falling"}.get(r.get("regime"), "mood_shaky")


def daily_cards(r: dict, profile: dict, today: dt.date | None = None, checkin_from_day: int = 5) -> list[dict]:
    lang, cur = profile.get("language", "en"), r.get("currency", "INR")
    first = (profile.get("name") or "").split()[0] if profile.get("name") else ""
    mp = r.get("monthly_plan") or {}
    today = today or dt.date.today()
    actions = []
    for o in mp.get("opportunistic", []):
        if o["status"] == "BUY":
            n = 3
            amt = o["budget_left"] / n
            dd = abs(round((o.get("off_high") or 0) * 100)) or _dd_from_msg(o["message"])
            actions.append({"text": f"<b>{t(lang, 'buy_title', name=o['name'])}</b>\n"
                                    f"{t(lang, 'buy_body', dd=dd, amt=_amt(amt, cur), n=n)}",
                            "buttons": [[(t(lang, "b_bought"), f"b|{o['symbol']}|{int(amt)}"),
                                         (t(lang, "b_skip"), f"s|{o['symbol']}"),
                                         (t(lang, "b_why"), f"w|{o['symbol']}")]]})
    for c in mp.get("core", []):
        if c["verdict"] == "CONTINUE + TOP-UP":
            dd = _dd_from_msg(c["why"])
            actions.append({"text": f"<b>{t(lang, 'topup_title', name=c['name'])}</b>\n"
                                    f"{t(lang, 'topup_body', dd=dd, amt=_amt(c['monthly'], cur))}",
                            "buttons": [[(t(lang, "b_bought"), f"b|{c['symbol']}|{int(c['monthly'])}"),
                                         (t(lang, "b_skip"), f"s|{c['symbol']}"),
                                         (t(lang, "b_why"), f"w|{c['symbol']}")]]})
        elif c["verdict"] == "REVIEW":
            actions.append({"text": f"<b>{t(lang, 'review_title', name=c['name'])}</b>\n{t(lang, 'review_body')}",
                            "buttons": [[(t(lang, "b_why"), f"w|{c['symbol']}")]]})
    if today.day >= checkin_from_day:
        for c in mp.get("pending", []):
            actions.append({"text": t(lang, "checkin", name=c["name"], amt=_amt(c["pending"], cur)),
                            "buttons": [[(t(lang, "b_yes"), f"y|{c['symbol']}|{int(c['pending'])}"),
                                         (t(lang, "b_no"), f"n|{c['symbol']}"),
                                         (t(lang, "b_other"), f"o|{c['symbol']}")]]})
    head = f"{t(lang, 'hello', name=(' ' + first) if first else '')}\n{t(lang, _mood(r))}"
    if not actions:
        return [{"text": f"{head}\n{t(lang, 'nothing')}", "buttons": []}]
    return [{"text": head, "buttons": []}] + actions


def _dd_from_msg(msg: str) -> int:
    import re
    m = re.search(r"-?(\d+)% (?:below|off)", msg)
    return int(m.group(1)) if m else 0


def why(r: dict, symbol: str, profile: dict) -> str:
    """Plain explanation for one item. Numbers are rounded; no jargon."""
    lang = profile.get("language", "en")
    st = next((s for s in r.get("stocks", []) if s["symbol"] == symbol), None)
    item = next((x for x in (r.get("monthly_plan") or {}).get("opportunistic", []) +
                 (r.get("monthly_plan") or {}).get("core", []) if str(x["symbol"]) == str(symbol)), {})
    name = (st or {}).get("name") or item.get("name") or symbol
    lines = [f"<b>{t(lang, 'why_head', name=name)}</b>"]
    if st:
        q = st["quality"]
        lines.append(f"• Business strength: {q:.0f}/10 " + ("(strong)" if q >= 7 else "(average)" if q >= 5 else "(weak)"))
        if st.get("off_high_52w") is not None:
            lines.append(f"• Price: {abs(st['off_high_52w']) * 100:.0f}% below its 1-year high")
        pe = st.get("forward_pe") or st.get("pe")
        if pe:
            lines.append(f"• You pay about {pe:.0f}× its yearly profit " + ("(cheap)" if pe < 18 else "(fair)" if pe < 30 else "(expensive)"))
        lenses = st.get("lenses", {})
        if lenses.get("buffett", {}).get("passed"):
            lines.append(f"• Warren Buffett-style checks passed: {lenses['buffett']['passed']}")
        w = {"bullish": "positive", "bearish": "weak", "neutral": "steady"}
        h = st["horizons"]
        lines.append(f"• Next 1-3 months: {w.get(h['short'], h['short'])}; next year: {w.get(h['medium'], h['medium'])}; "
                     f"long run: {w.get(h['long'], h['long'])}")
    if item.get("trigger") is not None:
        lines.append(f"• Your plan: start buying when it's {abs(item['trigger']) * 100:.0f}% or more below its high")
    elif item.get("why"):
        lines.append(f"• {item['why']}")
    lines.append("• Buy in 3 parts, not all at once, in case it falls further.")
    lines.append(f"<i>{t(lang, 'disclaimer')}</i>")
    return "\n".join(html.escape(x, quote=False) if not x.startswith(("<b>", "<i>")) else x for x in lines)


def month_view(r: dict, profile: dict) -> str:
    lang, cur = profile.get("language", "en"), r.get("currency", "INR")
    mp = r.get("monthly_plan") or {}
    try:
        label = dt.datetime.strptime(mp.get("month", ""), "%Y-%m").strftime("%B %Y")
    except ValueError:
        label = mp.get("month", "")
    lines = [f"<b>{t(lang, 'month_head', month=label)}</b>"]
    for c in mp.get("core", []):
        status = t(lang, "pending") if c["pending"] else t(lang, "done")
        lines.append(f"• {html.escape(c['name'], quote=False)}: {_amt(c['monthly'], cur)} — {status}")
    for o in mp.get("opportunistic", []):
        word = {"BUY": "🟢 buy", "WAIT": "⏳ wait", "DONE": "✅ done", "SKIP": "⛔ skip",
                "PAUSED": "⏸ paused", "CAPPED": "⚠️ too big"}.get(o["status"], o["status"].lower())
        lines.append(f"• {html.escape(o['name'], quote=False)}: {word}")
    return "\n".join(lines)


def menu(profile: dict) -> dict:
    lang = profile.get("language", "en")
    return {"text": t(lang, "menu"), "buttons": [[(t(lang, "m_today"), "m|today"), (t(lang, "m_month"), "m|month"),
                                                  (t(lang, "m_help"), "m|help")]]}
