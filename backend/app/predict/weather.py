"""Weather context adapter (fog warnings along the route).

Real source: India Meteorological Department (IMD) APIs at api.imd.gov.in. Access needs IP whitelisting
through IMD's request form and acceptance of IMD's terms; we do not have that, so `IMDWeatherProvider`
refuses with ProviderNotConfigured. In demo mode, `SimulatedWeatherProvider` serves clearly labelled
SIMULATED warnings from the scenario file. We never present simulated warnings as IMD data.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field

from app.core.clock import ensure_aware
from app.providers import ProviderNotConfigured


class FogSeverity(str, Enum):
    MODERATE = "MODERATE"
    DENSE = "DENSE"


class FogWarning(BaseModel):
    id: str
    severity: FogSeverity
    stations: list[str] = Field(default_factory=list)       # stations covered (both ends of a section = section)
    issued_at: datetime
    valid_from: datetime
    valid_to: datetime
    source: str                                             # e.g. "SIMULATED_DEMO (IMD-style warning)"
    source_url: str | None = None

    def valid_at(self, t: datetime) -> bool:
        t = ensure_aware(t, "t")
        return self.valid_from <= t <= self.valid_to

    def covers_section(self, a: str, b: str) -> bool:
        return a in self.stations and b in self.stations


class WeatherProvider(Protocol):
    name: str

    def fog_warnings(self, now: datetime) -> list[FogWarning]: ...


class SimulatedWeatherProvider:
    """Demo only: warnings written in the scenario file, labelled SIMULATED."""
    name = "SIMULATED_DEMO"

    def __init__(self, warnings: list[dict] | None):
        self._w = [FogWarning(**w) for w in (warnings or [])]

    def fog_warnings(self, now: datetime) -> list[FogWarning]:
        return list(self._w)


class IMDWeatherProvider:
    """Placeholder for IMD data. Needs IMD IP whitelisting + terms acceptance before it can be used."""
    name = "IMD"

    def fog_warnings(self, now: datetime) -> list[FogWarning]:
        raise ProviderNotConfigured("IMD API access requires IP whitelisting and acceptance of IMD terms")


class UnavailableWeatherProvider:
    """Used when weather is switched off or the provider failed: the engine says 'weather unavailable'."""
    name = "UNAVAILABLE"

    def fog_warnings(self, now: datetime) -> list[FogWarning]:
        raise ProviderNotConfigured("No weather provider configured")
