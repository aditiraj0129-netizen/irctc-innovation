"""Plain-language answers for the decision questions (EN / HI).

Every number in these sentences is copied from tool results (the delay engine, the connection engine, the
recovery engine and the rules engine). Nothing is calculated here except formatting.
"""
from __future__ import annotations

from datetime import datetime

from app.data.timetable import STATIONS
from app.explain.explainer import rupees, when

RISK = {"en": {"COMFORTABLE": "you should make it comfortably", "TIGHT": "it should work, but with little time to spare",
               "HIGH_RISK": "it is at risk: it works only if the delay does not grow",
               "UNLIKELY": "it is unlikely: it works only if the train wins back time",
               "NOT_FEASIBLE": "it is no longer possible", "INSUFFICIENT_INFORMATION": "I can't tell: live data is missing"},
        "hi": {"COMFORTABLE": "आप आराम से पकड़ लेंगे", "TIGHT": "पकड़ सकते हैं, पर समय कम रहेगा",
               "HIGH_RISK": "खतरा है: तभी चलेगा जब देरी और न बढ़े", "UNLIKELY": "मुश्किल है: तभी चलेगा जब ट्रेन समय वापस ले",
               "NOT_FEASIBLE": "अब संभव नहीं", "INSUFFICIENT_INFORMATION": "कह नहीं सकते: लाइव जानकारी नहीं है"}}

T = {
    "en": {
        "CATCH": "Train {t1} is {d} min late. It is expected at {stn} between {early} and {late} (most likely {mid}). "
                 "Your next train {t2} leaves at {dep}, and you need about {need} min to change. So {risk}.",
        "CATCH_WATCH": " Check again at {stn}: if it is more than {max} min late, the change will not work.",
        "NO_CONNECTION": "This journey has no change of train. Train {t1}: {state}.",
        "CANCEL": "If you cancel train {train} now: about {amount} back (charge {charge}), rule {rule}.",
        "CANCEL_DROP": " After {at} it becomes {after}.",
        "CANCEL_TDR": " Don't cancel yet: if you miss the connection because the first train was late, a TDR may return "
                      "{tdr} (if approved) — more than cancelling.",
        "CANCEL_NONE": "Your booked trains have already left, so there is nothing to cancel.",
        "CLAIM": " A TDR for the missed connection may return {tdr} if approved; file it by {by}.",
        "CLAIM_NO": " A TDR for the missed connection is not available here ({reason}).",
        "ANNOUNCED": " (This refund rule is announced but not yet officially confirmed.)",
        "TRAINS": "Other trains from {origin} (simulated timetable): {list}. Seats and fares are not checked; book on IRCTC.",
        "TRAIN_LINE": "{trains} at {dep}{frm}, arriving {arr}",
        "FROM": " from {stn} (about {m} min to get there)",
        "TRAINS_NONE": "No other train found for the rest of today.",
        "NEXT": " Next day: {list}.",
        "UR": "Unreserved option: train {train} at {dep} has General coaches. You need a separate unreserved ticket "
              "(UTS/RailOne or the counter) — your reserved ticket for {booked} is not valid on it — and you must stay "
              "in the General coach. Seats are not guaranteed.",
        "UR_NONE": "I found no same-day train with General coaches. Don't board a reserved coach without a valid ticket.",
        "BUS": "Demo sample only, not a real timetable: bus from {term} at {dep}, arriving about {arr} (sample fare "
               "{fare}). Check the bus operator for real times and seats.",
        "BUS_NONE": "Bus data is not connected yet, so I can't suggest a bus. Check the state transport website.",
        "BUS_NOT_FOUND": "No bus found in the next few hours (demo samples).",
        "TOMORROW": "Next day: {trains} at {dep}, arriving {arr}. Tatkal for it opens {opens} ({state}); it needs Aadhaar "
                    "OTP and is never guaranteed.",
        "TOMORROW_NONE": "I found no next-day train in the simulated timetable.",
        "REC_STAY_AND_WATCH": "Safest step: stay on your train. Check again at {stn}; if it is more than {max} min late, open the Decide screen again.",
        "REC_STAY_BUT_PREPARE": "Safest step: stay on your train, but get a backup ready: {backup}. Check at {stn}; if it is more than {max} min late, book the backup.",
        "REC_DONT_CANCEL": " Don't cancel your second ticket now: cancelling gives {cancel}, a TDR may give {tdr} if approved.",
        "REC_BOOK_ALTERNATIVE": "Safest step: book {option}.",
        "REC_TRAVEL_AS_BOOKED": "Safest step: travel as booked.",
        "REC_IF_NOT": " If you no longer want to travel, decide by {by}: cancelling then returns about {amount}.",
        "REC_FILE_TDR": "Safest step: don't travel and file a TDR before the train leaves: {amount} if approved.",
        "REC_AUTO": "Your refund comes automatically. Look at another train for the journey.",
        "REC_CHECK": "Live data is out of date or missing. Check NTES or RailOne, or call 139.",
        "REC_OVER": "Your journey is over.",
        "NO_ALT": "no other option found — call 139",
    },
    "hi": {
        "CATCH": "ट्रेन {t1} {d} मिनट लेट है। यह {stn} पर {early} से {late} के बीच पहुँचेगी (सबसे संभावित {mid})। "
                 "आपकी अगली ट्रेन {t2} {dep} पर छूटती है, और बदलने में लगभग {need} मिनट चाहिए। इसलिए {risk}।",
        "CATCH_WATCH": " {stn} पर फिर देखें: अगर {max} मिनट से ज़्यादा लेट हो, तो ट्रेन बदलना संभव नहीं होगा।",
        "NO_CONNECTION": "इस यात्रा में ट्रेन बदलनी नहीं है। ट्रेन {t1}: {state}।",
        "CANCEL": "अगर आप ट्रेन {train} अभी रद्द करें: लगभग {amount} वापस (कटौती {charge}), नियम {rule}।",
        "CANCEL_DROP": " {at} के बाद यह {after} हो जाएगा।",
        "CANCEL_TDR": " अभी रद्द न करें: अगर पहली ट्रेन लेट होने से कनेक्शन छूटे, तो TDR से {tdr} (मंज़ूरी पर) मिल सकता है — रद्द करने से ज़्यादा।",
        "CANCEL_NONE": "आपकी बुक ट्रेनें निकल चुकी हैं, इसलिए रद्द करने को कुछ नहीं।",
        "CLAIM": " छूटे कनेक्शन का TDR मंज़ूरी पर {tdr} दिला सकता है; {by} तक फाइल करें।",
        "CLAIM_NO": " यहाँ छूटे कनेक्शन का TDR उपलब्ध नहीं ({reason})।",
        "ANNOUNCED": " (यह नियम घोषित है, पर अभी आधिकारिक रूप से पक्का नहीं।)",
        "TRAINS": "{origin} से दूसरी ट्रेनें (सिम्युलेटेड समय-सारणी): {list}। सीट और किराया जाँचा नहीं गया; IRCTC पर बुक करें।",
        "TRAIN_LINE": "{trains} {dep} पर{frm}, पहुँच {arr}",
        "FROM": " ({stn} से, वहाँ पहुँचने में लगभग {m} मिनट)",
        "TRAINS_NONE": "आज के लिए कोई दूसरी ट्रेन नहीं मिली।",
        "NEXT": " अगले दिन: {list}।",
        "UR": "अनारक्षित विकल्प: ट्रेन {train} ({dep}) में जनरल डिब्बे हैं। अलग अनारक्षित टिकट चाहिए (UTS/RailOne या काउंटर) — "
              "{booked} का आरक्षित टिकट इस पर मान्य नहीं — और जनरल डिब्बे में ही रहना होगा। सीट की गारंटी नहीं।",
        "UR_NONE": "आज जनरल डिब्बे वाली कोई ट्रेन नहीं मिली। बिना मान्य टिकट आरक्षित डिब्बे में न चढ़ें।",
        "BUS": "सिर्फ़ डेमो नमूना, असली समय-सारणी नहीं: {term} से {dep} पर बस, लगभग {arr} पहुँच (नमूना किराया {fare})। असली समय और सीट बस ऑपरेटर से जाँचें।",
        "BUS_NONE": "बस की जानकारी अभी जुड़ी नहीं है। राज्य परिवहन की वेबसाइट देखें।",
        "BUS_NOT_FOUND": "अगले कुछ घंटों में कोई बस नहीं मिली (डेमो नमूने)।",
        "TOMORROW": "अगले दिन: {trains} {dep} पर, पहुँच {arr}। इसका तत्काल {opens} पर खुलता है ({state}); आधार OTP चाहिए और गारंटी कभी नहीं।",
        "TOMORROW_NONE": "सिम्युलेटेड समय-सारणी में अगले दिन की कोई ट्रेन नहीं मिली।",
        "REC_STAY_AND_WATCH": "सबसे सुरक्षित कदम: अपनी ट्रेन में रहें। {stn} पर फिर देखें; अगर {max} मिनट से ज़्यादा लेट हो, तो निर्णय स्क्रीन फिर खोलें।",
        "REC_STAY_BUT_PREPARE": "सबसे सुरक्षित कदम: अपनी ट्रेन में रहें, पर एक बैकअप तैयार रखें: {backup}। {stn} पर देखें; अगर {max} मिनट से ज़्यादा लेट हो, तो बैकअप बुक करें।",
        "REC_DONT_CANCEL": " दूसरा टिकट अभी रद्द न करें: रद्द करने पर {cancel}, TDR से मंज़ूरी पर {tdr} मिल सकता है।",
        "REC_BOOK_ALTERNATIVE": "सबसे सुरक्षित कदम: {option} बुक करें।",
        "REC_TRAVEL_AS_BOOKED": "सबसे सुरक्षित कदम: जैसा बुक है वैसे यात्रा करें।",
        "REC_IF_NOT": " अगर अब यात्रा नहीं करनी, तो {by} तक तय करें: तब रद्द करने पर लगभग {amount} वापस।",
        "REC_FILE_TDR": "सबसे सुरक्षित कदम: यात्रा न करें और ट्रेन छूटने से पहले TDR फाइल करें: मंज़ूरी पर {amount}।",
        "REC_AUTO": "आपका रिफंड अपने-आप आएगा। यात्रा के लिए दूसरी ट्रेन देखें।",
        "REC_CHECK": "लाइव जानकारी पुरानी या नहीं है। NTES या RailOne देखें, या 139 पर कॉल करें।",
        "REC_OVER": "आपकी यात्रा पूरी हो गई।",
        "NO_ALT": "कोई दूसरा विकल्प नहीं मिला — 139 पर कॉल करें",
    },
}
STATE = {"en": {"TRAIN_LATE": "running late", "ON_TRACK": "on track", "TRAIN_CANCELLED": "cancelled",
                "NOT_CONFIRMED": "ticket not confirmed", "STALE": "data out of date"},
         "hi": {"TRAIN_LATE": "लेट चल रही", "ON_TRACK": "समय पर", "TRAIN_CANCELLED": "रद्द",
                "NOT_CONFIRMED": "टिकट पक्का नहीं", "STALE": "जानकारी पुरानी"}}


def _t(iso: str | None) -> str:
    return when(datetime.fromisoformat(iso)) if iso else "-"


def _stn(code: str | None, lang: str) -> str:
    return STATIONS.get(code or "", {}).get(lang, code or "")


def _line(o: dict, L: dict, lang: str = "en") -> str:
    frm = L["FROM"].format(stn=_stn(o["from"], lang), m=o["access_minutes"]) if o.get("access_minutes") else ""
    return L["TRAIN_LINE"].format(trains=" + ".join(o["trains"]) or "-", dep=_t(o["departure"]), arr=_t(o["arrival"]),
                                  frm=frm)


def answer(intent: str, r: dict, lang: str) -> tuple[str, list[str]]:
    """Return (text, rule_ids) for a decision intent from tool results `r`."""
    L = T[lang]
    if intent == "CATCH_CONNECTION":
        p = r.get("predict_delay") or {}
        c, pr, h = p.get("connection"), p.get("prediction"), p.get("header") or {}
        if not c:
            return L["NO_CONNECTION"].format(t1=h.get("first_train", "-"),
                                             state=STATE[lang].get(h.get("status"), h.get("status") or "-")), []
        if c["risk"] == "INSUFFICIENT_INFORMATION" or not pr or not pr.get("expected_arrival"):
            return L["REC_CHECK"], []
        txt = L["CATCH"].format(t1=c["from_train"], d=pr["current_delay_minutes"], stn=_stn(c["station"], lang),
                                early=_t(pr["arrival_early"]), late=_t(pr["arrival_late"]), mid=_t(pr["expected_arrival"]),
                                t2=c["to_train"], dep=_t(c["next_departure"]), need=c["transfer_minutes_needed"],
                                risk=RISK[lang][c["risk"]])
        if c.get("watch") and c["risk"] not in ("NOT_FEASIBLE", "UNLIKELY"):
            txt += L["CATCH_WATCH"].format(stn=_stn(c["watch"]["station"], lang), max=c["watch"]["max_delay_minutes"])
        return txt, []
    if intent == "CANCEL_MONEY":
        cmp = r.get("compare_decisions") or {}
        card = next((x for x in cmp.get("cards", []) if x["key"] == "CANCEL"), None)
        claims = cmp.get("claims") or {}
        rows = {m["key"]: m for m in cmp.get("money", [])}
        rules: list[str] = []
        if card is None or card["status"] != "AVAILABLE":
            txt = L["CANCEL_NONE"]
        else:
            m, o = card["money"], card["outcome"]
            rules += m.get("rule_ids", [])
            txt = L["CANCEL"].format(train=o["train"], amount=rupees(m["paise"]), charge=rupees(m["charge_paise"]),
                                     rule=(m.get("rule_ids") or ["-"])[0])
            later = rows.get("CANCEL_LATER")
            if later and later["applicable"] and later["money_back_paise"] is not None:
                txt += L["CANCEL_DROP"].format(at=_t(later["at"]), after=rupees(later["money_back_paise"]))
            if m.get("legal_status") == "ANNOUNCED":
                txt += L["ANNOUNCED"]
            if card["next_action"].get("code") == "DO_NOT_CANCEL_TDR_BETTER":
                txt += L["CANCEL_TDR"].format(tdr=rupees(card["next_action"]["tdr_paise"]))
                rules.append(card["next_action"].get("rule") or "TDR-MISSED-CONNECTION")
                return txt, rules
        claim = rows.get("KEEP_AND_CLAIM")
        if claim and claim["applicable"] and claim["money_back_paise"]:
            txt += L["CLAIM"].format(tdr=rupees(claim["money_back_paise"]), by=_t(claim["deadline"]))
            rules += claim["rule_ids"]
        elif claims.get("tdr_eligibility") == "NOT_ELIGIBLE":
            txt += L["CLAIM_NO"].format(reason=(claims.get("tdr_reason") or "").replace("_", " ").lower())
        return txt, rules
    if intent == "FIND_TRAIN":
        a = r.get("find_alternatives") or {}
        opts, nd = a.get("options", []), a.get("next_day", [])
        txt = (L["TRAINS"].format(origin=_stn(a.get("origin"), lang), list="; ".join(_line(o, L, lang) for o in opts[:3]))
               if opts else L["TRAINS_NONE"])
        if nd:
            txt += L["NEXT"].format(list="; ".join(_line(o, L, lang) for o in nd[:2]))
        return txt, []
    if intent == "UNRESERVED":
        u = r.get("check_unreserved") or {}
        if not u.get("options"):
            return L["UR_NONE"], ["GUIDE-UNRESERVED"]
        o = u["options"][0]
        dep = _t(o["departure"]) + (L["FROM"].format(stn=_stn(o["from"], lang), m=o["access_minutes"])
                                    if o.get("access_minutes") else "")
        return L["UR"].format(train=" + ".join(o["trains"]), dep=dep, booked=u.get("booked_train", "-")), \
            ["GUIDE-UNRESERVED"]
    if intent == "BUS":
        b = r.get("find_bus") or {}
        if b.get("status") == "NOT_CONFIGURED":
            return L["BUS_NONE"], []
        if not b.get("options"):
            return L["BUS_NOT_FOUND"], []
        o = b["options"][0]
        return L["BUS"].format(term=o.get("terminal", "-"), dep=_t(o["departure"]), arr=_t(o["arrival"]),
                               fare=rupees(o["fare_paise"] or 0)), []
    if intent == "NEXT_DAY":
        n = r.get("next_day_options") or {}
        if not n.get("options"):
            return L["TOMORROW_NONE"], ["GUIDE-TATKAL"]
        o = n["options"][0]
        tk = o.get("tatkal") or {}
        state = {"en": {"OPEN_NOW": "already open", "OPENS_LATER": "not open yet"},
                 "hi": {"OPEN_NOW": "खुल चुका", "OPENS_LATER": "अभी नहीं खुला"}}[lang].get(tk.get("state"), "-")
        return L["TOMORROW"].format(trains=" + ".join(o["trains"]), dep=_t(o["departure"]), arr=_t(o["arrival"]),
                                    opens=_t(tk.get("opens_at")), state=state), ["GUIDE-TATKAL"]
    if intent == "SAFEST":
        cmp = r.get("compare_decisions") or {}
        rec = cmp.get("recommendation") or {}
        code = rec.get("code")
        rules: list[str] = []
        if code in ("STAY_AND_WATCH", "STAY_BUT_PREPARE"):
            w = rec.get("watch") or {}
            b = rec.get("backup")
            txt = L["REC_" + code].format(stn=_stn(w.get("station"), lang), max=w.get("max_delay_minutes", "-"),
                                          backup=(f"{b['train']} {_t(b['dep'])} → {_t(b['arr'])}" if b else L["NO_ALT"]))
            if rec.get("dont_cancel"):
                txt += L["REC_DONT_CANCEL"].format(cancel=rupees(rec["dont_cancel"]["cancel_paise"]),
                                                   tdr=rupees(rec["dont_cancel"]["tdr_paise"]))
                rules.append("TDR-MISSED-CONNECTION")
            return txt, rules
        if code == "BOOK_ALTERNATIVE":
            o = rec.get("option") or {}
            txt = L["REC_BOOK_ALTERNATIVE"].format(option=f"{o.get('train')} {_t(o.get('dep'))} → {_t(o.get('arr'))}")
            cl = rec.get("claim") or {}
            if cl.get("code") == "FILE_TDR_MISSED_CONNECTION":
                txt += L["CLAIM"].format(tdr=rupees(cl["paise"]), by=_t(cl.get("deadline")))
                rules.append("TDR-MISSED-CONNECTION")
            if rec.get("tatkal"):
                rules.append("GUIDE-TATKAL")
            return txt, rules
        if code == "TRAVEL_AS_BOOKED":
            txt = L["REC_TRAVEL_AS_BOOKED"]
            inn = rec.get("if_not_travelling")
            if inn and inn.get("decide_by"):
                txt += L["REC_IF_NOT"].format(by=_t(inn["decide_by"]), amount=rupees(inn["cancel_paise"]))
            return txt, rules
        if code == "FILE_TDR_BEFORE_DEPARTURE":
            return L["REC_FILE_TDR"].format(amount=rupees((rec.get("claim") or {}).get("paise") or 0)), ["TDR-LATE-3H"]
        if code == "AUTO_REFUND_FIND_TRAIN":
            return L["REC_AUTO"], []
        if code == "JOURNEY_OVER":
            return L["REC_OVER"], []
        return L["REC_CHECK"], []
    return "", []
