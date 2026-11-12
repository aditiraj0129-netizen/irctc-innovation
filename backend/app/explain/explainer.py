"""Plan explanations: LLM first (optional), template always as the fallback.

The LLM is NEVER allowed to write a number, time or amount. It writes slot
names like {refund}; our code fills them from the rules engine. A validator
rejects any reply that breaks this, and we fall back to the template.
"""
from __future__ import annotations

import json
import os
import re
from datetime import datetime
from typing import Protocol

import httpx
from pydantic import BaseModel

from app.data.timetable import STATIONS
from app.explain.templates import T
from app.plan.models import Plan, PlanKind

SLOT_RE = re.compile(r"\{([a-z_]+)\}")
DIGIT_RE = re.compile(r"[0-9०-९]")
BANNED = ["guarantee", "guaranteed", "assured", "definitely", "100%", "pakka", "गारंटी", "पक्का", "निश्चित रूप से"]
ALLOWED_TOKENS_WITH_DIGITS = ["139"]       # the official enquiry number may appear in fixed text
MAX_LEN = 360


class Explanation(BaseModel):
    plan_id: str
    lang: str
    headline: str
    body: str
    source: str                 # "llm" or "template"
    validator_errors: list[str] = []


# ---------- formatting (code, not AI) ----------

def rupees(paise: int) -> str:
    r = paise // 100
    s = str(r)
    if len(s) > 3:                                  # Indian grouping: 1,23,456
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts) + "," + tail
    p = paise % 100
    return f"₹{s}" + (f".{p:02d}" if p else "")


def when(dt: datetime | None) -> str:
    return dt.strftime("%H:%M, %d %b") if dt else ""


def slot_values(plan: Plan, lang: str) -> dict[str, str]:
    station = plan.rides[0].from_stn if plan.rides else ""
    return {
        "refund": rupees(plan.money_back_paise),
        "deadline": when(plan.deadline),
        "arrival": when(plan.arrival),
        "trains": " + ".join(f"{r.train_no} {r.train_name}" for r in plan.rides),
        "station": STATIONS.get(station, {}).get(lang, station),
    }


def fill(text: str, values: dict[str, str]) -> str:
    return SLOT_RE.sub(lambda m: values.get(m.group(1), ""), text)


# ---------- validation ----------

def validate(headline: str, body: str, allowed_slots: set[str]) -> list[str]:
    errors = []
    for part in (headline, body):
        stripped = SLOT_RE.sub("", part)
        for tok in ALLOWED_TOKENS_WITH_DIGITS:
            stripped = stripped.replace(tok, "")
        if DIGIT_RE.search(stripped):
            errors.append("DIGIT_OUTSIDE_SLOT")
        for s in SLOT_RE.findall(part):
            if s not in allowed_slots:
                errors.append(f"UNKNOWN_SLOT:{s}")
        low = part.lower()
        if any(b in low for b in BANNED):
            errors.append("PROMISE_WORDING")
    if not headline.strip() or not body.strip():
        errors.append("EMPTY")
    if len(headline) + len(body) > MAX_LEN:
        errors.append("TOO_LONG")
    return sorted(set(errors))


# ---------- LLM client ----------

class LLMClient(Protocol):
    def complete_json(self, system: str, user: str) -> dict: ...


SYSTEM_PROMPT = (
    "You explain a railway decision to a first-time Indian train passenger in {lang_name}. "
    "Use ONLY the facts in the JSON. Write every amount, time, date, train number and percentage "
    "ONLY as one of these slot names, exactly: {slots}. Never write digits. "
    "Never promise a refund: say 'if approved' when the JSON says if_approved is true. "
    "Max 2 short sentences in the body and a headline of max 8 words. "
    'Reply with JSON only: {{"headline": "...", "body": "..."}}'
)


class HttpLLM:
    """Works with Anthropic or any OpenAI-compatible API, chosen by env vars."""

    def __init__(self, provider: str, model: str, api_key: str, base_url: str | None = None, timeout: float = 4.0):
        self.provider, self.model, self.api_key = provider, model, api_key
        self.base_url, self.timeout = base_url, timeout

    def complete_json(self, system: str, user: str) -> dict:
        if self.provider == "anthropic":
            r = httpx.post(self.base_url or "https://api.anthropic.com/v1/messages", timeout=self.timeout,
                           headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01",
                                    "content-type": "application/json"},
                           json={"model": self.model, "max_tokens": 300, "system": system,
                                 "messages": [{"role": "user", "content": user}]})
            r.raise_for_status()
            text = "".join(b.get("text", "") for b in r.json()["content"])
        else:
            r = httpx.post((self.base_url or "https://api.openai.com/v1") + "/chat/completions",
                           timeout=self.timeout, headers={"Authorization": f"Bearer {self.api_key}"},
                           json={"model": self.model, "response_format": {"type": "json_object"},
                                 "messages": [{"role": "system", "content": system},
                                              {"role": "user", "content": user}]})
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"]
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise ValueError("no JSON in reply")
        return json.loads(match.group(0))


def llm_from_env() -> LLMClient | None:
    if os.getenv("LLM_ENABLED", "false").lower() != "true":
        return None
    key, model = os.getenv("LLM_API_KEY"), os.getenv("LLM_MODEL")
    if not key or not model:
        return None
    return HttpLLM(os.getenv("LLM_PROVIDER", "anthropic"), model, key, os.getenv("LLM_BASE_URL"),
                   float(os.getenv("LLM_TIMEOUT_SECONDS", "4")))


# ---------- main entry ----------

def _facts(plan: Plan) -> dict:
    return {
        "action": plan.kind.value, "travels": plan.travels, "if_approved": plan.money_back_if_approved,
        "needs_new_ticket": plan.needs_new_ticket, "seat_availability_checked": False,
        "has_deadline": plan.deadline is not None, "warnings": plan.warnings,
        "slots_meaning": {"refund": "money back", "deadline": "act-by time", "arrival": "arrival time",
                          "trains": "train(s) to take", "station": "station to change at"},
    }


def _allowed_slots(plan: Plan) -> set[str]:
    s = {"refund"}
    if plan.deadline:
        s.add("deadline")
    if plan.arrival:
        s.add("arrival")
    if plan.rides:
        s |= {"trains", "station"}
    return s


def template_explanation(plan: Plan, lang: str, errors: list[str] | None = None) -> Explanation:
    head, body = T[lang][plan.kind]
    v = slot_values(plan, lang)
    return Explanation(plan_id=plan.id, lang=lang, headline=fill(head, v), body=fill(body, v),
                       source="template", validator_errors=errors or [])


_cache: dict[tuple, Explanation] = {}


def explain(plan: Plan, lang: str = "en", llm: LLMClient | None = None) -> Explanation:
    if lang not in T:
        raise ValueError("lang must be 'en' or 'hi'")
    if llm is None or plan.kind == PlanKind.USE_OFFICIAL_CHANNEL:
        return template_explanation(plan, lang)
    key = (plan.kind, plan.travels, plan.money_back_if_approved, bool(plan.deadline), bool(plan.rides), lang,
           tuple(plan.warnings))
    if key in _cache:
        cached = _cache[key]
        v = slot_values(plan, lang)
        return Explanation(plan_id=plan.id, lang=lang, headline=fill(cached.headline, v),
                           body=fill(cached.body, v), source="llm")
    slots = _allowed_slots(plan)
    system = SYSTEM_PROMPT.format(lang_name="Hindi" if lang == "hi" else "simple English",
                                  slots=", ".join("{" + s + "}" for s in sorted(slots)))
    try:
        reply = llm.complete_json(system, json.dumps(_facts(plan)))
        head, body = str(reply.get("headline", "")), str(reply.get("body", ""))
    except Exception as e:                                   # timeout, HTTP error, bad JSON
        return template_explanation(plan, lang, [f"LLM_ERROR:{type(e).__name__}"])
    errors = validate(head, body, slots)
    if errors:
        return template_explanation(plan, lang, errors)
    _cache[key] = Explanation(plan_id=plan.id, lang=lang, headline=head, body=body, source="llm")
    v = slot_values(plan, lang)
    return Explanation(plan_id=plan.id, lang=lang, headline=fill(head, v), body=fill(body, v), source="llm")
