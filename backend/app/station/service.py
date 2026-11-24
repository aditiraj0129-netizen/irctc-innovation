"""One place that builds the journey's station view (used by the API and by the Copilot tools)."""
from __future__ import annotations

from datetime import datetime

from app.domain.models import Event, Journey
from app.plan.transfer import PassengerProfile
from app.predict.delay import DelayPrediction
from app.station import graph
from app.station.feasibility import StationConnection, assess_connection
from app.station.platforms import PlatformInfo, PlatformObservation, platform_info
from app.station.route import Profile, Route, RouteError, route
from app.twin.twin import build_twin

FACILITY_TYPES = ["TICKET_COUNTER", "ATVM", "ENQUIRY", "HELP_DESK", "WAITING_ROOM", "RETIRING_ROOM", "WASHROOM",
                  "DRINKING_WATER", "FOOD", "CLOAKROOM", "RPF", "PARKING", "METRO", "EXIT"]


def journey_station_view(journey: Journey, events: list[Event], now: datetime, profile: PassengerProfile | None,
                         obs: list[PlatformObservation], pred: DelayPrediction | None, at: str | None = None,
                         route_profile: Profile | None = None, buffer: int = 5, at_source: str = "MANUAL") -> dict:
    twin = build_twin(journey, events, now, profile)
    idx = next((i for i, tl in enumerate(twin.legs) if tl.state.value != "ARRIVED"), len(journey.legs) - 1)
    conn: StationConnection | None = None
    if idx + 1 < len(journey.legs):
        conn = assess_connection(journey, idx + 1, pred, events, now, obs, profile, buffer, route_profile, at, at_source)
        code, arrival, departure = journey.legs[idx].to_stn, conn.arrival_platform, conn.departure_platform
    else:
        code = journey.legs[-1].to_stn
        arrival, departure = platform_info(journey.legs[-1].train_no, code, "ARRIVAL", obs, now), None
    return {"station": code, "station_obj": graph.get(code), "connection": conn, "arrival": arrival,
            "departure": departure, "first_train": journey.legs[idx].train_no,
            "second_train": journey.legs[idx + 1].train_no if idx + 1 < len(journey.legs) else None}


def nearest_facility(code: str, start: str, ftype: str, profile: Profile = Profile.FASTEST,
                     speed: str = "normal") -> tuple[Route | None, list[str]]:
    """Closest mapped facility of a type (by expected walking time). EXIT means any entrance/exit."""
    st = graph.get(code)
    if st is None or start not in st.nodes:
        return None, []
    targets = [n.id for n in st.nodes.values()
               if (ftype == "EXIT" and n.kind.value == "SIDE") or (n.facility_type == ftype)]
    best = None
    for t in targets:
        try:
            r = route(st, start, t, profile, speed)
        except RouteError:
            continue
        if r.found and (best is None or (r.minutes_low + r.minutes_high) < (best.minutes_low + best.minutes_high)):
            best = r
    return best, targets


def start_node(view: dict, from_platform: int | None = None) -> str | None:
    """Where a Copilot route starts: a platform the passenger named, else the arrival platform if known."""
    st = view["station_obj"]
    if st is None:
        return None
    if from_platform and f"PF{from_platform}" in st.nodes:
        return f"PF{from_platform}"
    a: PlatformInfo = view["arrival"]
    return f"PF{a.platform}" if a and a.platform and f"PF{a.platform}" in st.nodes else None
