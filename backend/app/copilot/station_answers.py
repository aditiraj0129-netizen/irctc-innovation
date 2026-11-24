"""Plain-language answers for station questions (EN / HI). Every value comes from tool results:
platforms from the platform service (with their status), routes and times from the route engine.
Unknown stays unknown."""
from __future__ import annotations

from datetime import datetime

from app.data.timetable import STATIONS
from app.explain.explainer import when

UNAVAILABLE = {"en": "Live platform information is currently unavailable. Please verify station display boards and announcements.",
               "hi": "लाइव प्लेटफॉर्म जानकारी अभी उपलब्ध नहीं है। कृपया स्टेशन के डिस्प्ले बोर्ड और घोषणाएँ देखें।"}
STATUS = {"en": {"CONFIRMED": "confirmed", "REPORTED": "reported, not confirmed", "SCHEDULED": "scheduled only, not live",
                 "PREDICTED": "predicted from recent runs, not live", "UNKNOWN": "unknown"},
          "hi": {"CONFIRMED": "पक्का", "REPORTED": "बताया गया, पक्का नहीं", "SCHEDULED": "सिर्फ़ समय-सारणी के अनुसार, लाइव नहीं",
                 "PREDICTED": "पिछली यात्राओं से अनुमान, लाइव नहीं", "UNKNOWN": "पता नहीं"}}
FAC = {"en": {"EXIT": "exit", "TICKET_COUNTER": "ticket counter", "ATVM": "ticket vending machine", "ENQUIRY": "enquiry counter",
              "HELP_DESK": "help desk", "WAITING_ROOM": "waiting room", "RETIRING_ROOM": "retiring room", "WASHROOM": "washroom",
              "DRINKING_WATER": "drinking water", "FOOD": "food stall", "CLOAKROOM": "cloakroom (luggage room)", "RPF": "RPF help point",
              "PARKING": "parking / pickup", "METRO": "metro connection"},
       "hi": {"EXIT": "निकास", "TICKET_COUNTER": "टिकट काउंटर", "ATVM": "टिकट वेंडिंग मशीन", "ENQUIRY": "पूछताछ काउंटर",
              "HELP_DESK": "सहायता डेस्क", "WAITING_ROOM": "प्रतीक्षालय", "RETIRING_ROOM": "विश्राम कक्ष", "WASHROOM": "शौचालय",
              "DRINKING_WATER": "पीने का पानी", "FOOD": "खाने का स्टॉल", "CLOAKROOM": "क्लॉकरूम (सामान घर)", "RPF": "RPF सहायता",
              "PARKING": "पार्किंग / पिकअप", "METRO": "मेट्रो"}}
T = {
    "en": {
        "ARR": "Train {train} is expected at {stn} on Platform {p} ({status}{age}).",
        "DEP": "Your next train {train} is expected from Platform {p} at {stn} ({status}{age}).",
        "CHANGED": " It changed from Platform {old}.",
        "VERIFY": " Verify on the station boards before moving.",
        "NO_DEP": "This journey has no connecting train.",
        "ROUTE": "From {a} to {b} at {stn}: about {lo}–{hi} min on foot ({m} m), {stairs} stair flight(s), {lifts} lift(s).",
        "ROUTE_STEPS": " Steps: {steps}.",
        "LIFT_UNKNOWN": " Lift working status is unknown — if it isn't working, use the stairs or ask staff.",
        "SCHEMATIC": " (Schematic map, not an official station map.)",
        "NO_STEP_FREE": "I couldn't find a route without stairs on our station map. Ask station staff or the help desk for assistance.",
        "NO_MAP": "I don't have a map for {stn} yet.",
        "LOC": "Tell me which platform you are on (for example: \"I am on Platform 4\"), then I can find the route.",
        "DEST": "I don't know which platform you want. Tell me the platform number.",
        "FAC": "Nearest {f}: {name}. From {a}: about {lo}–{hi} min ({m} m).",
        "FAC_ILLUS": " Its position on our map is illustrative — check the station signs.",
        "FAC_NONE": "I have no mapped {f} at {stn}. Ask at the enquiry counter.",
        "s_UP": "go up the {via} to the {to}", "s_DOWN": "go down the {via} to {to}", "s_CROSS_FOB": "cross the {fob}",
        "s_WALK_PLATFORM": "walk along the platform ({m} m)", "s_WALK_CONCOURSE": "walk along the concourse ({m} m)",
        "s_WALK_LINK": "follow the {name} ({m} m)", "s_TO_SIDE": "go to the {name}", "s_ENTER_PLATFORM": "enter {p}",
        "s_TO_CONCOURSE": "go to the concourse", "v_STAIRS": "stairs", "v_LIFT": "lift", "v_ESCALATOR": "escalator",
    },
    "hi": {
        "ARR": "ट्रेन {train} के {stn} पर प्लेटफॉर्म {p} पर आने की उम्मीद है ({status}{age})।",
        "DEP": "आपकी अगली ट्रेन {train} के {stn} पर प्लेटफॉर्म {p} से छूटने की उम्मीद है ({status}{age})।",
        "CHANGED": " यह प्लेटफॉर्म {old} से बदला है।",
        "VERIFY": " चलने से पहले स्टेशन के बोर्ड पर ज़रूर देखें।",
        "NO_DEP": "इस यात्रा में कोई कनेक्टिंग ट्रेन नहीं है।",
        "ROUTE": "{stn} पर {a} से {b}: पैदल लगभग {lo}–{hi} मिनट ({m} मीटर), {stairs} सीढ़ी, {lifts} लिफ्ट।",
        "ROUTE_STEPS": " कदम: {steps}।",
        "LIFT_UNKNOWN": " लिफ्ट चालू है या नहीं, पता नहीं — न चले तो सीढ़ी लें या स्टाफ से पूछें।",
        "SCHEMATIC": " (योजनाबद्ध नक्शा, आधिकारिक स्टेशन नक्शा नहीं।)",
        "NO_STEP_FREE": "हमारे नक्शे पर बिना सीढ़ी का रास्ता नहीं मिला। स्टेशन स्टाफ या सहायता डेस्क से मदद लें।",
        "NO_MAP": "{stn} का नक्शा अभी हमारे पास नहीं है।",
        "LOC": "बताइए आप किस प्लेटफॉर्म पर हैं (जैसे: \"मैं प्लेटफॉर्म 4 पर हूँ\"), फिर मैं रास्ता बताऊँगा।",
        "DEST": "आपको किस प्लेटफॉर्म पर जाना है, पता नहीं। प्लेटफॉर्म नंबर बताइए।",
        "FAC": "सबसे पास {f}: {name}। {a} से: लगभग {lo}–{hi} मिनट ({m} मीटर)।",
        "FAC_ILLUS": " नक्शे पर इसकी जगह अनुमानित है — स्टेशन के संकेत देखें।",
        "FAC_NONE": "{stn} पर हमारे नक्शे में कोई {f} नहीं है। पूछताछ काउंटर पर पूछें।",
        "s_UP": "{via} से ऊपर {to} पर जाएँ", "s_DOWN": "{via} से नीचे {to} पर जाएँ", "s_CROSS_FOB": "{fob} पार करें",
        "s_WALK_PLATFORM": "प्लेटफॉर्म पर चलें ({m} मीटर)", "s_WALK_CONCOURSE": "कॉनकोर्स में चलें ({m} मीटर)",
        "s_WALK_LINK": "{name} से जाएँ ({m} मीटर)", "s_TO_SIDE": "{name} की ओर जाएँ", "s_ENTER_PLATFORM": "{p} पर जाएँ",
        "s_TO_CONCOURSE": "कॉनकोर्स में जाएँ", "v_STAIRS": "सीढ़ी", "v_LIFT": "लिफ्ट", "v_ESCALATOR": "एस्केलेटर",
    },
}


def _stn(code: str, lang: str) -> str:
    return STATIONS.get(code, {}).get(lang, code)


def _lab(d: dict | None, lang: str) -> str:
    return (d or {}).get(lang) or (d or {}).get("en") or ""


def _plats(refs: list[int], lang: str) -> str:
    w = "Platform" if lang == "en" else "प्लेटफॉर्म"
    return f"{w} {refs[0]}" if len(refs) == 1 else f"{w} {refs[0]}–{refs[-1]}"


def steps_text(route: dict, lang: str) -> str:
    L, out = T[lang], []
    for s in route["steps"]:
        p, c = s["params"], s["code"]
        if c in ("START", "ARRIVE"):
            continue
        if c in ("UP", "DOWN"):
            out.append(L["s_" + c].format(via=L["v_" + p["via"]], to=_lab(p["to"], lang)))
        elif c == "CROSS_FOB":
            out.append(L["s_CROSS_FOB"].format(fob=_lab(p["fob"], lang)))
        elif c in ("WALK_PLATFORM", "WALK_CONCOURSE"):
            out.append(L["s_" + c].format(m=p.get("m", 0)))
        elif c == "WALK_LINK":
            out.append(L["s_WALK_LINK"].format(name=_lab(p.get("name"), lang), m=p.get("m", 0)))
        elif c == "TO_SIDE":
            out.append(L["s_TO_SIDE"].format(name=_lab(p["name"], lang)))
        elif c == "ENTER_PLATFORM":
            out.append(L["s_ENTER_PLATFORM"].format(p=_plats(p["platforms"], lang)))
        elif c == "TO_CONCOURSE":
            out.append(L["s_TO_CONCOURSE"])
    return "; ".join(out)


def _platform_line(key: str, info: dict, train: str, lang: str) -> str:
    L = T[lang]
    if not info or info["platform"] is None:
        return UNAVAILABLE[lang]
    age = (f", {info['age_minutes']} min ago" if lang == "en" else f", {info['age_minutes']} मिनट पहले") \
        if info.get("age_minutes") is not None else ""
    txt = L[key].format(train=train, stn=_stn(info["station"], lang), p=info["platform"],
                        status=STATUS[lang][info["status"]], age=age)
    if info.get("changed_from"):
        txt += L["CHANGED"].format(old=info["changed_from"])
    if info["status"] != "CONFIRMED" or info.get("stale"):
        txt += L["VERIFY"] if info["status"] in ("CONFIRMED", "REPORTED") else " " + UNAVAILABLE[lang]
    return txt


def answer(intent: str, r: dict, lang: str, params: dict) -> str:
    L = T[lang]
    if intent in ("PLATFORM_ARRIVAL", "PLATFORM_DEPARTURE"):
        g = r.get("get_platforms") or {}
        if intent == "PLATFORM_ARRIVAL":
            return _platform_line("ARR", g.get("arrival"), g.get("first_train", "-"), lang)
        if not g.get("second_train"):
            return L["NO_DEP"]
        return _platform_line("DEP", g.get("departure"), g["second_train"], lang)
    if intent == "STATION_ROUTE":
        res = r.get("station_route") or {}
        if not res.get("route"):
            reason = res.get("reason")
            return {"NO_STATION_MAP": L["NO_MAP"].format(stn=_stn(res.get("station", ""), lang)),
                    "LOCATION_UNKNOWN": L["LOC"], "DESTINATION_PLATFORM_UNKNOWN": L["DEST"],
                    "INVALID_PLATFORM": L["DEST"]}.get(reason, L["LOC"])
        rt = res["route"]
        if not rt["found"]:
            return L["NO_STEP_FREE"]
        txt = L["ROUTE"].format(a=_lab(rt["start_label"], lang), b=_lab(rt["end_label"], lang),
                                stn=_stn(res["station"], lang), lo=rt["minutes_low"], hi=rt["minutes_high"],
                                m=rt["distance_m"], stairs=rt["stairs"], lifts=rt["lifts"])
        txt += L["ROUTE_STEPS"].format(steps=steps_text(rt, lang))
        if rt["lifts"]:
            txt += L["LIFT_UNKNOWN"]
        return txt + L["SCHEMATIC"]
    if intent == "STATION_FACILITY":
        res = r.get("find_facility") or {}
        f = FAC[lang].get(params.get("type", ""), params.get("type", ""))
        if not res.get("found"):
            reason = res.get("reason")
            if reason == "LOCATION_UNKNOWN":
                return L["LOC"]
            if reason == "NO_STATION_MAP":
                return L["NO_MAP"].format(stn=_stn(res.get("station", ""), lang))
            return L["FAC_NONE"].format(f=f, stn=_stn(res.get("station", ""), lang))
        rt, n = res["route"], res["facility"]
        txt = L["FAC"].format(f=f, name=_lab(n["label"], lang), a=_lab(rt["start_label"], lang), lo=rt["minutes_low"],
                              hi=rt["minutes_high"], m=rt["distance_m"])
        if n["verification"] == "ILLUSTRATIVE":
            txt += L["FAC_ILLUS"]
        return txt + L["SCHEMATIC"]
    return ""
