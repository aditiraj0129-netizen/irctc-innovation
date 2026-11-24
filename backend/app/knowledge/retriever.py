"""Retrieval over the railway knowledge corpus.

`Retriever` is the interface the rest of the app uses. Today it is implemented with BM25 (lexical ranking)
plus a small English/Hindi/Hinglish synonym map, because no embedding model can be downloaded in the build
environment and the corpus is small. An embedding retriever (for example pgvector on PostgreSQL) can implement
the same interface later without changing any caller.

Retrieved text is DATA, never instructions: callers quote it with its citation and never execute it.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

from pydantic import BaseModel

from app.knowledge.corpus import Chunk, corpus

# Canonical terms for words passengers actually type (English, Hindi, Hinglish).
SYNONYMS = {
    "late": ["late", "delay", "delayed", "der", "deri", "लेट", "देर", "देरी", "running"],
    "refund": ["refund", "money", "paisa", "paise", "wapas", "vapas", "रिफंड", "पैसा", "पैसे", "वापस", "fare"],
    "cancel": ["cancel", "cancelled", "cancellation", "radd", "रद्द", "cancelling"],
    "waitlisted": ["waitlist", "waitlisted", "waiting", "wl", "वेटिंग", "प्रतीक्षा"],
    "chart": ["chart", "चार्ट"],
    "tdr": ["tdr", "टीडीआर", "claim", "file", "filing", "filed"],
    "connection": ["connection", "connecting", "linked", "missed", "miss", "chhoot", "chhut", "छूट", "कनेक्शन"],
    "hours": ["hours", "hour", "ghante", "ghanta", "घंटे", "घंटा"],
    "deadline": ["deadline", "kab", "कब", "before", "time", "limit"],
    "help": ["help", "helpline", "complaint", "madad", "मदद", "139", "railmadad"],
    "simulated": ["simulated", "live", "real", "data", "source", "official", "ntes", "irctc"],
    "vandebharat": ["vande", "bharat", "sleeper", "amrit"],
}
_CANON = {w: k for k, ws in SYNONYMS.items() for w in ws}
STOP = {"the", "a", "an", "is", "of", "to", "and", "or", "in", "on", "for", "my", "i", "me", "it", "be", "if",
        "what", "how", "do", "does", "can", "will", "are", "this", "that", "with", "kya", "hai", "ka", "ki", "ke",
        "मेरी", "मेरा", "क्या", "है", "की", "का", "के", "में", "से"}


def tokens(text: str) -> list[str]:
    raw = re.findall(r"[\wऀ-ॿ]+", text.lower())
    return [_CANON.get(w, w) for w in raw if w not in STOP and len(w) > 1]


class Hit(BaseModel):
    chunk: Chunk
    score: float


class Retriever(Protocol):
    def search(self, query: str, k: int = 3, applies_to: str | None = None,
               as_of: str | None = None) -> list[Hit]: ...


class BM25Retriever:
    def __init__(self, chunks: list[Chunk], k1: float = 1.4, b: float = 0.75):
        self.chunks = chunks
        self.docs = [tokens(c.title + " " + c.text) for c in chunks]
        self.k1, self.b = k1, b
        self.avg = sum(len(d) for d in self.docs) / max(len(self.docs), 1)
        df = Counter(t for d in self.docs for t in set(d))
        n = len(self.docs)
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}
        self.tf = [Counter(d) for d in self.docs]

    def search(self, query: str, k: int = 3, applies_to: str | None = None,
               as_of: str | None = None) -> list[Hit]:
        """as_of (YYYY-MM-DD): skip rules that were not in force on that date (old or future versions)."""
        q = tokens(query)
        hits = []
        for i, c in enumerate(self.chunks):
            if applies_to and applies_to not in c.applies_to and "ALL" not in c.applies_to:
                continue
            if as_of and (c.effective_from > as_of or (c.effective_to and c.effective_to < as_of)):
                continue
            tf, dl = self.tf[i], len(self.docs[i])
            s = sum(self.idf.get(t, 0) * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * dl / self.avg))
                    for t in q if t in tf)
            if s > 0:
                hits.append(Hit(chunk=c, score=round(s, 3)))
        hits.sort(key=lambda h: -h.score)
        return hits[:k]


_default: Retriever | None = None


def default_retriever() -> Retriever:
    global _default
    if _default is None:
        _default = BM25Retriever(corpus()[1])
    return _default
