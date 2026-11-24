"""Provider interfaces: the seams where authorised real data and AI services plug in later.

Today every provider is the SIMULATED one. The OFFICIAL ones are deliberate stubs: they explain what
authorisation is needed and raise, so the app can never silently pretend to have live railway access.
Nothing here scrapes or calls private railway systems.

Select with PROVIDER_MODE=simulated (default). Any other value fails at start-up with a clear message.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Protocol

from app.data.source import SimulatedSource, Scenario
from app.data.timetable import STATIONS
from app.domain.models import Event, Journey
from app.explain.explainer import LLMClient, llm_from_env
from app.knowledge.retriever import Retriever, default_retriever
from app.plan.service import registry
from app.plan.transfer import station_info
from app.rules.engine import RuleRegistry


class ProviderNotConfigured(RuntimeError):
    pass


class TrainStatusProvider(Protocol):
    def events_for(self, journey_id: str) -> list[Event]: ...


class JourneyProvider(Protocol):
    def journey_for_pnr(self, pnr: str) -> Journey: ...


class StationInfoProvider(Protocol):
    def name(self, code: str, lang: str = "en") -> str: ...
    def transfer_estimate(self, code: str) -> dict: ...


class RulesProvider(Protocol):
    def registry(self) -> RuleRegistry: ...


# ---------- simulated implementations (used now) ----------

class SimulatedTrainStatus:
    label = "SIMULATED"

    def __init__(self, source: SimulatedSource):
        self.source = source

    def events_for(self, journey_id: str) -> list[Event]:
        return self.source.events_for(journey_id)


class SimulatedJourneys:
    label = "SIMULATED"

    def __init__(self, source: SimulatedSource):
        self.source = source

    def journey_for_pnr(self, pnr: str) -> Journey:
        return self.source.get_journey(pnr)


class StaticStations:
    label = "SIMULATED_ESTIMATES"

    def name(self, code: str, lang: str = "en") -> str:
        return STATIONS.get(code, {}).get(lang, code)

    def transfer_estimate(self, code: str) -> dict:
        return station_info(code)


class YamlRules:
    label = "VERSIONED_YAML"

    def registry(self) -> RuleRegistry:
        return registry()


# ---------- official stubs (need authorisation; never scrape) ----------

class OfficialTrainStatus:
    """Would read running status from an AUTHORISED NTES/CRIS feed. Not available to this project."""

    def events_for(self, journey_id: str) -> list[Event]:
        raise ProviderNotConfigured("Live train status needs an authorised NTES/CRIS data agreement.")


class OfficialJourneys:
    """Would read a passenger's booking with their consent through an AUTHORISED IRCTC integration."""

    def journey_for_pnr(self, pnr: str) -> Journey:
        raise ProviderNotConfigured("PNR lookup needs an authorised IRCTC integration and passenger consent.")


@dataclass
class Providers:
    mode: str
    train_status: TrainStatusProvider
    journeys: JourneyProvider
    stations: StationInfoProvider
    rules: RulesProvider
    ai_model: LLMClient | None
    retrieval: Retriever

    def describe(self) -> dict:
        return {"mode": self.mode,
                "train_status": getattr(self.train_status, "label", type(self.train_status).__name__),
                "journeys": getattr(self.journeys, "label", type(self.journeys).__name__),
                "stations": getattr(self.stations, "label", type(self.stations).__name__),
                "rules": getattr(self.rules, "label", type(self.rules).__name__),
                "ai_model": "CONFIGURED" if self.ai_model else "OFF (deterministic fallback)",
                "retrieval": type(self.retrieval).__name__}


def build_providers(source: SimulatedSource, mode: str | None = None) -> Providers:
    mode = (mode or os.getenv("PROVIDER_MODE", "simulated")).lower()
    if mode != "simulated":
        raise ProviderNotConfigured(f"PROVIDER_MODE={mode} is not available: only 'simulated' is implemented. "
                                    "Official providers need authorised railway data access.")
    return Providers(mode=mode, train_status=SimulatedTrainStatus(source), journeys=SimulatedJourneys(source),
                     stations=StaticStations(), rules=YamlRules(), ai_model=llm_from_env(),
                     retrieval=default_retriever())
