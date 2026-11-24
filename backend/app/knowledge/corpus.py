"""Railway knowledge corpus for retrieval (RAG).

Two kinds of documents:
1. RULE documents generated from `rules/data/rulesets.yaml`, the same file the rules engine uses. So the
   knowledge the assistant cites can never disagree with the amounts the engine calculates.
2. Curated documents in `knowledge/docs/*.md` (help channels, TDR basics, data trust). They are written in
   our own words, each with front-matter metadata: source URL, publisher, effective date, version, applicability
   and verification status.

Official PDFs could not be downloaded in the build environment, so documents are summaries with links, not copies.
"""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from app.rules.engine import RuleRegistry, unresolved_conditions

DOCS_DIR = Path(__file__).parent / "docs"


class Document(BaseModel):
    id: str
    title: str
    publisher: str
    source_url: str
    effective_from: str
    effective_to: str | None = None
    version: str
    applies_to: list[str]
    status: str            # NOTIFIED | ANNOUNCED | NEEDS_VERIFICATION | GENERAL_GUIDANCE | SUMMARY_OF_VERIFIED_RULE
    unresolved: list[str] = Field(default_factory=list)
    text: str


class Chunk(BaseModel):
    chunk_id: str
    doc_id: str
    title: str
    text: str
    source_url: str
    effective_from: str
    effective_to: str | None = None
    version: str
    applies_to: list[str]
    status: str
    unresolved: list[str]


def _rupees(paise: int) -> str:
    return f"₹{paise // 100:,}"


def _rule_docs() -> list[Document]:
    reg = RuleRegistry.from_yaml()
    out: list[Document] = []
    for rs in reg.data.rule_sets:
        lines = [f"{rs.name}. Applies to {', '.join(c.value for c in rs.train_categories)} trains from {rs.effective_from}."]
        for s in rs.confirmed_slabs:
            h = None if s.min_hours is None else (int(s.min_hours) if float(s.min_hours).is_integer() else s.min_hours)
            when = (f"more than {h} hours before departure" if s.min_hours is not None and not s.min_inclusive
                    else f"at least {h} hours before departure (and not earlier than the previous window)"
                    if s.min_hours is not None
                    else "within the last window before departure")
            if s.type.value == "FLAT":
                what = "a flat charge per passenger is deducted (for example " + \
                       ", ".join(f"{k.value} {_rupees(v)}" for k, v in list(rs.flat_charge_paise.items())[:4]) + ")"
            elif s.type.value == "PERCENT":
                what = f"{s.percent}% of the fare is deducted" + (" (at least the flat charge)" if s.min_flat else "")
            else:
                what = "no refund is given on cancellation"
            lines.append(f"If a confirmed ticket is cancelled {when}, {what}.")
        if rs.clerkage_paise_per_passenger:
            lines.append(f"Clerkage is {_rupees(rs.clerkage_paise_per_passenger)} per passenger.")
        if rs.source.note:
            lines.append(f"Note: {rs.source.note}")
        out.append(Document(id=rs.id, title=rs.name, publisher=rs.source.title, source_url=rs.source.url,
                            effective_from=str(rs.effective_from), version=rs.version,
                            effective_to=str(rs.effective_to) if rs.effective_to else None,
                            applies_to=[c.value for c in rs.train_categories], status=rs.legal_status.value,
                            unresolved=unresolved_conditions(rs), text=" ".join(lines)))
    for r in reg.data.special_rules:
        text = r.name + "."
        if r.source.note:
            text += " " + r.source.note
        out.append(Document(id=r.id, title=r.name, publisher=r.source.title, source_url=r.source.url,
                            effective_from=str(r.effective_from), version=r.version,
                            effective_to=str(r.effective_to) if r.effective_to else None,
                            applies_to=[c.value for c in r.train_categories], status=r.legal_status.value,
                            unresolved=unresolved_conditions(r), text=text))
        if r.needs_verification and "NEEDS_VERIFICATION" not in out[-1].status:
            out[-1].status = "NEEDS_VERIFICATION"
    return out


def _md_docs() -> list[Document]:
    out = []
    for f in sorted(DOCS_DIR.glob("*.md")):
        raw = f.read_text(encoding="utf-8")
        m = re.match(r"^---\n(.*?)\n---\n(.*)$", raw, re.S)
        if not m:
            raise ValueError(f"{f.name}: missing front matter")
        meta = yaml.safe_load(m.group(1))
        meta["effective_from"] = str(meta["effective_from"])
        out.append(Document(**meta, text=" ".join(m.group(2).split())))
    return out


def _sentences(text: str) -> list[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def chunk(doc: Document, max_words: int = 70) -> list[Chunk]:
    """Split on sentence boundaries into chunks of about `max_words` words; metadata goes with every chunk."""
    chunks, cur = [], []
    for s in _sentences(doc.text):
        if cur and sum(len(x.split()) for x in cur) + len(s.split()) > max_words:
            chunks.append(" ".join(cur))
            cur = cur[-1:]                       # one-sentence overlap keeps context across chunks
        cur.append(s)
    if cur:
        chunks.append(" ".join(cur))
    meta = doc.model_dump(exclude={"text", "id", "publisher"})
    return [Chunk(chunk_id=f"{doc.id}#{i + 1}", doc_id=doc.id, text=t, **meta) for i, t in enumerate(chunks)]


# Text that tries to instruct an AI has no place in a rules corpus. Such chunks are dropped at ingestion,
# so a tampered document can't smuggle instructions into answers (defence against indirect prompt injection).
INJECTION = re.compile(r"ignore (all |any |the )?(previous|prior|above) (instructions|rules)|system prompt|you are now|"
                       r"disregard (the|all|your)|act as|developer mode|reveal your", re.I)


def safe_chunks(chunks: list[Chunk]) -> list[Chunk]:
    return [c for c in chunks if not INJECTION.search(c.text) and not INJECTION.search(c.title)]


@lru_cache(maxsize=1)
def corpus() -> tuple[list[Document], list[Chunk]]:
    docs = _rule_docs() + _md_docs()
    return docs, safe_chunks([c for d in docs for c in chunk(d)])
