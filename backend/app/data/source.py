"""Railway data sources.

Everything the app knows about trains comes through RailDataSource.
  * SimulatedSource: reads demo scenario files. Used now.
  * OfficialSource: an empty placeholder. Real PNR, running-status and
    availability data would need approval from IRCTC / CRIS. We do NOT
    assume that any public API exists, and we never scrape.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from app.core.clock import IST, ensure_aware
from app.data.timetable import load_stops, scheduled_times, train_names
from app.domain.models import Event, EventSource, Journey, Leg
from app.rules.models import Ticket

SCENARIO_DIR = Path(__file__).parent / "scenarios"


class RailDataSource(Protocol):
    def get_journey(self, pnr: str) -> Journey: ...
    def get_events(self) -> list[Event]: ...


class UnknownPNRError(LookupError):
    pass


class Scenario:
    """One demo scenario: a journey, its events and the starting clock time."""

    def __init__(self, raw: dict):
        self.raw = raw
        self.id: str = raw["id"]
        self.title: dict = raw["title"]
        self.pnr: str = raw["pnr"]
        self.start_clock: datetime = ensure_aware(datetime.fromisoformat(raw["start_clock"]), "start_clock")
        self.group: str | None = raw.get("group")
        stops = load_stops()
        names = train_names(stops)
        legs = []
        for i, l in enumerate(raw["legs"], start=1):
            run = date.fromisoformat(l["run_date"])
            dep, arr = scheduled_times(stops, l["train_no"], run, l["from"], l["to"])
            ticket = Ticket(train_no=l["train_no"], train_category=l.get("category", "REGULAR"),
                            travel_class=l["class"], quota=l.get("quota", "GENERAL"), status=l["status"],
                            is_eticket=l.get("is_eticket", True), scheduled_departure=dep,
                            fare_per_passenger_paise=l["fare_paise"], passengers=l["passengers"])
            legs.append(Leg(seq=i, ticket=ticket, train_name=names[l["train_no"]],
                            from_stn=l["from"], to_stn=l["to"], scheduled_arrival=arr))
        self.journey = Journey(id=self.id, pnr_label=f"{self.pnr[:2]}xxxxxx{self.pnr[-2:]} (simulated)",
                               title=self.title["en"], legs=legs, linked_pnr=raw.get("linked_pnr", False),
                               vikalp_opted=raw.get("vikalp_opted", False),
                               min_transfer_minutes=raw.get("min_transfer_minutes", 30))
        self.events = [Event(**{**e, "source": EventSource.SIMULATED}) for e in raw.get("events", [])]
        # Observations of OTHER trains on the network (used only by the delay engine's congestion indicator).
        self.network_events = [Event(**{**e, "source": EventSource.SIMULATED}) for e in raw.get("network_events", [])]
        # Demo-only simulated fog warnings (never real IMD data).
        self.weather_warnings: list[dict] = list(raw.get("weather_warnings", []))
        # Simulated platform observations (status CONFIRMED / REPORTED), labelled by source.
        from app.station.platforms import PlatformObservation
        self.platform_events = [PlatformObservation(**p) for p in raw.get("platform_events", [])]


def load_scenarios() -> dict[str, Scenario]:
    out = {}
    for f in sorted(SCENARIO_DIR.glob("*.json")):
        sc = Scenario(json.loads(f.read_text(encoding="utf-8")))
        out[sc.id] = sc
    return out


class SimulatedSource:
    """Holds one active scenario. The presenter panel can add events live."""

    def __init__(self, scenarios: dict[str, Scenario]):
        self.scenarios = scenarios
        self.by_pnr = {s.pnr: s for s in scenarios.values()}
        self.extra_events: dict[str, list[Event]] = {k: [] for k in scenarios}

    def scenario_for_pnr(self, pnr: str) -> Scenario:
        if pnr not in self.by_pnr:
            raise UnknownPNRError("PNR not found in the demo data")
        return self.by_pnr[pnr]

    def get_journey(self, pnr: str) -> Journey:
        return self.scenario_for_pnr(pnr).journey

    def events_for(self, scenario_id: str) -> list[Event]:
        return [*self.scenarios[scenario_id].events, *self.extra_events[scenario_id]]

    def add_event(self, scenario_id: str, event: Event) -> None:
        self.extra_events[scenario_id].append(event)

    def reset(self, scenario_id: str) -> None:
        self.extra_events[scenario_id] = []


class OfficialSource:
    """Placeholder for authorised IRCTC / CRIS data. Not implemented on purpose."""

    def get_journey(self, pnr: str) -> Journey:
        raise NotImplementedError("Requires an authorised data agreement with IRCTC/CRIS")

    def get_events(self) -> list[Event]:
        raise NotImplementedError("Requires an authorised data agreement with IRCTC/CRIS")
