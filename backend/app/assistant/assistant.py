"""Multilingual passenger assistant (text in, text out; the browser adds voice).

1. Work out what the passenger is asking (an "intent") with simple keyword rules
   in English, Hindi and Hinglish. An LLM may OPTIONALLY classify questions the
   rules don't understand, but only into this fixed list of intents.
2. Answer ONLY from facts the backend already calculated (plans, wallet, twin).
   Amounts, deadlines and train status are never produced by an LLM.

New languages: add a block to KEYWORDS and ANSWERS; nothing else changes.
"""
from __future__ import annotations

import json
import re
from enum import Enum

from pydantic import BaseModel, Field

from app.data.timetable import STATIONS
from app.explain.explainer import LLMClient, rupees, when
from app.plan.models import Plan
from app.twin.twin import JourneyTwin
from app.wallet.wallet import Stage, Wallet


class Intent(str, Enum):
    MISS_CONNECTION = "MISS_CONNECTION"
    DEADLINE = "DEADLINE"
    REFUND = "REFUND"
    WAIT_OR_ALTERNATIVE = "WAIT_OR_ALTERNATIVE"
    WHAT_TO_DO = "WHAT_TO_DO"
    STATUS = "STATUS"
    UNKNOWN = "UNKNOWN"


# Checked in this order: the more specific intents come first.
KEYWORDS: dict[Intent, list[str]] = {
    Intent.MISS_CONNECTION: ["connecting", "connection", "miss my", "missed", "chhoot", "chhut", "chut jaye", "छूट",
                             "कनेक्शन", "दूसरी ट्रेन छूट"],
    Intent.DEADLINE: ["deadline", "by when", "last time", "kab tak", "when is", "समय सीमा", "कब तक", "आखिरी समय"],
    Intent.REFUND: ["refund", "money back", "paisa", "paise", "kitna milega", "how much", "रिफंड", "पैसा", "पैसे", "कितना"],
    Intent.WAIT_OR_ALTERNATIVE: ["wait", "another train", "other train", "alternative", "dusri train", "doosri train",
                                 "intezaar", "intezar", "ruk", "दूसरी ट्रेन", "इंतज़ार", "इंतजार", "रुक"],
    Intent.WHAT_TO_DO: ["what should i do", "what do i do", "kya karun", "kya karu", "kya karoon", "ab kya",
                        "क्या करूँ", "क्या करूं", "क्या करें", "अब क्या"],
    Intent.STATUS: ["status", "late", "delay", "kitni der", "where is", "लेट", "देरी", "कितनी देर"],
}


def detect_intent(text: str) -> Intent:
    t = re.sub(r"\s+", " ", text.lower()).strip()
    for intent, words in KEYWORDS.items():
        if any(w in t for w in words):
            return intent
    return Intent.UNKNOWN


ANSWERS = {
    "en": {
        "NO_ADVICE": "Live data is out of date, so I can't advise safely. Check RailOne or NTES, or call 139.",
        "BEST": "Best option now: {plan}.",
        "MONEY": "{amount} back{approval}.",
        "ACT_BY": "Act by {deadline}.",
        "ARRIVE": "You would reach at {arrival}.",
        "NO_DEADLINE": "There is no refund deadline right now.",
        "DEADLINE_ITEM": "{kind}: by {deadline}{unverified}.",
        "REFUND_ITEM": "{kind}: about {amount}{approval} (estimate, stage: {stage}).",
        "NO_REFUND": "No refund applies right now under the current rule.",
        "STATUS": "Train {train}: {state}, {delay}.",
        "ON_TIME": "no delay reported",
        "LATE": "{minutes} min late",
        "CONN_OK": "Your change at {station} looks {cls} ({margin} min to spare).",
        "CONN_BAD": "Your change at {station} is {cls}. {best}",
        "NO_CONN": "This journey has no change of train.",
        "WAIT": "If you wait, you keep your ticket; the top option is {plan}. Alternatives need a new ticket and seats are not checked.",
        "UNKNOWN": "I can answer: what to do now, wait or another train, missed connection, refund amount, deadlines, and train status.",
        "approval": " if approved",
        "unverified": " (deadline not yet officially confirmed)",
        "rules_note": "Amounts come from rule {rules}. A TDR refund is decided by the Zonal Railway.",
    },
    "hi": {
        "NO_ADVICE": "लाइव डेटा पुराना है, इसलिए मैं सुरक्षित सलाह नहीं दे सकता। RailOne या NTES देखें, या 139 पर कॉल करें।",
        "BEST": "अभी सबसे अच्छा विकल्प: {plan}।",
        "MONEY": "{amount} वापस{approval}।",
        "ACT_BY": "{deadline} तक करें।",
        "ARRIVE": "आप {arrival} तक पहुँचेंगे।",
        "NO_DEADLINE": "अभी कोई रिफंड समय-सीमा नहीं है।",
        "DEADLINE_ITEM": "{kind}: {deadline} तक{unverified}।",
        "REFUND_ITEM": "{kind}: लगभग {amount}{approval} (अनुमान, स्थिति: {stage})।",
        "NO_REFUND": "मौजूदा नियम के अनुसार अभी कोई रिफंड नहीं।",
        "STATUS": "ट्रेन {train}: {state}, {delay}।",
        "ON_TIME": "कोई देरी नहीं",
        "LATE": "{minutes} मिनट लेट",
        "CONN_OK": "{station} पर ट्रेन बदलना {cls} लगता है ({margin} मिनट बचे)।",
        "CONN_BAD": "{station} पर ट्रेन बदलना {cls} है। {best}",
        "NO_CONN": "इस यात्रा में ट्रेन नहीं बदलनी है।",
        "WAIT": "रुकने पर आपका टिकट बना रहता है; सबसे ऊपर का विकल्प है {plan}। दूसरी ट्रेन के लिए नया टिकट चाहिए, सीटें जाँची नहीं गईं।",
        "UNKNOWN": "मैं बता सकता हूँ: अब क्या करें, रुकें या दूसरी ट्रेन, छूटा कनेक्शन, रिफंड, समय-सीमा और ट्रेन की स्थिति।",
        "approval": " मंज़ूरी मिलने पर",
        "unverified": " (समय-सीमा अभी आधिकारिक रूप से पक्की नहीं)",
        "rules_note": "राशि नियम {rules} से है। TDR रिफंड का फैसला ज़ोनल रेलवे करता है।",
    },
}

PLAN_NAMES = {
    "en": {"TRAVEL_AS_BOOKED": "travel as booked", "TRAVEL_DELAYED": "wait for your delayed train",
           "CANCEL_NOW": "cancel now", "FILE_TDR_LATE": "don't travel and file a TDR",
           "TDR_LATE_PLUS_ALTERNATIVE": "file a TDR and take another train",
           "AUTO_REFUND_WAIT": "do nothing, the refund is automatic",
           "AUTO_REFUND_PLUS_ALTERNATIVE": "take another train (refund is automatic)",
           "TDR_MISSED_CONNECTION_ONLY": "stop and file a TDR for the missed train",
           "TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE": "take another train and file a TDR for the missed one",
           "CANCEL_NEXT_LEG_PLUS_ALTERNATIVE": "cancel the next train and rebook",
           "USE_OFFICIAL_CHANNEL": "check the official channel"},
    "hi": {"TRAVEL_AS_BOOKED": "बुक की गई यात्रा करें", "TRAVEL_DELAYED": "अपनी लेट ट्रेन का इंतज़ार करें",
           "CANCEL_NOW": "अभी कैंसिल करें", "FILE_TDR_LATE": "यात्रा न करें और TDR फाइल करें",
           "TDR_LATE_PLUS_ALTERNATIVE": "TDR फाइल करें और दूसरी ट्रेन लें",
           "AUTO_REFUND_WAIT": "कुछ न करें, रिफंड अपने आप आएगा",
           "AUTO_REFUND_PLUS_ALTERNATIVE": "दूसरी ट्रेन लें (रिफंड अपने आप)",
           "TDR_MISSED_CONNECTION_ONLY": "रुकें और छूटी ट्रेन का TDR फाइल करें",
           "TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE": "दूसरी ट्रेन लें और छूटी ट्रेन का TDR फाइल करें",
           "CANCEL_NEXT_LEG_PLUS_ALTERNATIVE": "अगली ट्रेन कैंसिल करके दोबारा बुक करें",
           "USE_OFFICIAL_CHANNEL": "आधिकारिक माध्यम से जाँचें"},
}

CLASS_NAMES = {"en": {"COMFORTABLE": "comfortable", "TIGHT": "tight", "HIGH_RISK": "high-risk",
                      "NOT_FEASIBLE": "not possible"},
               "hi": {"COMFORTABLE": "आरामदायक", "TIGHT": "कम समय वाला", "HIGH_RISK": "जोखिम भरा",
                      "NOT_FEASIBLE": "संभव नहीं"}}


class AssistantFact(BaseModel):
    label: str
    value: str
    rule_ids: list[str] = Field(default_factory=list)


class AssistantReply(BaseModel):
    intent: Intent
    intent_source: str                 # keywords, llm, none
    lang: str
    answer: str
    facts: list[AssistantFact]
    rule_ids: list[str]
    answer_source: str = "RULES_ENGINE"   # the answer text is built from calculated facts only
    data_label: str = "SIMULATED"


def _classify_with_llm(llm: LLMClient, text: str) -> Intent:
    system = ("Classify a railway passenger's question into exactly one of: "
              + ", ".join(i.value for i in Intent) + '. Reply JSON {"intent": "..."} only.')
    try:
        val = str(llm.complete_json(system, json.dumps({"question": text[:300]})).get("intent", ""))
        return Intent(val) if val in Intent.__members__ else Intent.UNKNOWN
    except Exception:
        return Intent.UNKNOWN


def answer(text: str, lang: str, plans: list[Plan], wallet: Wallet, twin: JourneyTwin, stale: bool,
           llm: LLMClient | None = None) -> AssistantReply:
    if lang not in ANSWERS:
        raise ValueError("lang must be en or hi")
    A, P = ANSWERS[lang], PLAN_NAMES[lang]
    intent, source = detect_intent(text), "keywords"
    if intent == Intent.UNKNOWN and llm is not None:
        intent, source = _classify_with_llm(llm, text), "llm"
    if intent == Intent.UNKNOWN:
        source = "none"
    facts: list[AssistantFact] = []
    rules: list[str] = []
    top = plans[0] if plans else None

    def best_text() -> str:
        if top is None:
            return ""
        parts = [A["BEST"].format(plan=P[top.kind.value])]
        if top.money_back_paise:
            parts.append(A["MONEY"].format(amount=rupees(top.money_back_paise),
                                           approval=A["approval"] if top.money_back_if_approved else ""))
        if top.deadline:
            parts.append(A["ACT_BY"].format(deadline=when(top.deadline)))
        if top.travels and top.arrival:
            parts.append(A["ARRIVE"].format(arrival=when(top.arrival)))
        rules.extend(r for d in top.decisions for r in d.rule_ids)
        facts.append(AssistantFact(label="TOP_PLAN", value=top.kind.value,
                                   rule_ids=[r for d in top.decisions for r in d.rule_ids]))
        return " ".join(parts)

    if stale or (top is not None and top.kind.value == "USE_OFFICIAL_CHANNEL"):
        msg = A["NO_ADVICE"]
    elif intent == Intent.WHAT_TO_DO:
        msg = best_text()
    elif intent == Intent.WAIT_OR_ALTERNATIVE:
        msg = A["WAIT"].format(plan=P[top.kind.value]) + " " + best_text() if top else A["UNKNOWN"]
    elif intent == Intent.MISS_CONNECTION:
        if not twin.transfers:
            msg = A["NO_CONN"]
        else:
            t = twin.transfers[0].check
            st = STATIONS.get(t.station, {}).get(lang, t.station)
            cls = CLASS_NAMES[lang][t.cls.value]
            facts.append(AssistantFact(label="TRANSFER", value=f"{st} {t.cls.value} {t.margin_minutes}"))
            msg = (A["CONN_BAD"].format(station=st, cls=cls, best=best_text())
                   if t.cls.value in ("NOT_FEASIBLE", "HIGH_RISK")
                   else A["CONN_OK"].format(station=st, cls=cls, margin=t.margin_minutes))
    elif intent == Intent.DEADLINE:
        items = [i for i in wallet.items if i.deadline and i.stage in (Stage.ESTIMATE, Stage.ELIGIBLE_TO_FILE)]
        if not items:
            msg = A["NO_DEADLINE"]
        else:
            msg = " ".join(A["DEADLINE_ITEM"].format(kind=i.kind, deadline=when(i.deadline),
                                                     unverified=A["unverified"] if i.deadline_unverified else "")
                           for i in items)
            for i in items:
                rules.extend(i.rule.rule_ids)
                facts.append(AssistantFact(label="DEADLINE", value=i.deadline.isoformat(), rule_ids=i.rule.rule_ids))
    elif intent == Intent.REFUND:
        items = [i for i in wallet.items if i.estimated_refund_paise > 0]
        if not items:
            msg = A["NO_REFUND"]
        else:
            msg = " ".join(A["REFUND_ITEM"].format(kind=i.kind, amount=rupees(i.estimated_refund_paise),
                                                   approval=A["approval"] if i.if_approved else "", stage=i.stage.value)
                           for i in items)
            for i in items:
                rules.extend(i.rule.rule_ids)
                facts.append(AssistantFact(label="REFUND_ESTIMATE", value=str(i.estimated_refund_paise),
                                           rule_ids=i.rule.rule_ids))
    elif intent == Intent.STATUS:
        msg = " ".join(A["STATUS"].format(train=l.train_no, state=l.state.value,
                                          delay=A["LATE"].format(minutes=l.delay_minutes) if l.delay_minutes
                                          else A["ON_TIME"]) for l in twin.legs)
        facts += [AssistantFact(label="LEG_STATE", value=f"{l.train_no} {l.state.value} {l.delay_minutes}")
                  for l in twin.legs]
    else:
        msg = A["UNKNOWN"]
    rules = list(dict.fromkeys(rules))
    if rules and msg != A["NO_ADVICE"]:
        msg += " " + A["rules_note"].format(rules=", ".join(rules))
    return AssistantReply(intent=intent, intent_source=source, lang=lang, answer=msg.strip(), facts=facts,
                          rule_ids=rules)
