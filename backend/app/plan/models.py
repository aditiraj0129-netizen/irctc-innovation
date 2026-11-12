from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

from app.plan.transfer import RISK_ORDER, TransferCheck, TransferClass
from app.rules.models import Decision


class PlanKind(str, Enum):
    TRAVEL_AS_BOOKED = "TRAVEL_AS_BOOKED"
    TRAVEL_DELAYED = "TRAVEL_DELAYED"
    CANCEL_NOW = "CANCEL_NOW"
    FILE_TDR_LATE = "FILE_TDR_LATE"
    TDR_LATE_PLUS_ALTERNATIVE = "TDR_LATE_PLUS_ALTERNATIVE"
    AUTO_REFUND_WAIT = "AUTO_REFUND_WAIT"
    AUTO_REFUND_PLUS_ALTERNATIVE = "AUTO_REFUND_PLUS_ALTERNATIVE"
    TDR_MISSED_CONNECTION_ONLY = "TDR_MISSED_CONNECTION_ONLY"
    TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE = "TDR_MISSED_CONNECTION_PLUS_ALTERNATIVE"
    CANCEL_NEXT_LEG_PLUS_ALTERNATIVE = "CANCEL_NEXT_LEG_PLUS_ALTERNATIVE"
    USE_OFFICIAL_CHANNEL = "USE_OFFICIAL_CHANNEL"


class Certainty(int, Enum):
    """Higher is more certain. Simulated availability is never shown as confirmed."""
    UNCERTAIN = 0
    CHECK_AVAILABILITY = 1      # alternative train: seats NOT checked (no live data)
    IF_APPROVED = 2             # TDR: depends on the Zonal Railway's decision
    AUTOMATIC = 3               # automatic refund under the rules
    BOOKED = 4                  # travelling on the ticket you already hold


class RideOut(BaseModel):
    train_no: str
    train_name: str
    from_stn: str
    dep: datetime
    to_stn: str
    arr: datetime


class Plan(BaseModel):
    id: str
    kind: PlanKind
    travels: bool
    arrival: datetime | None = None
    rides: list[RideOut] = Field(default_factory=list)
    money_back_paise: int = 0
    money_back_if_approved: bool = False
    money_lost_paise: int = 0          # of what was already paid
    needs_new_ticket: bool = False     # new fare is NOT included in money figures
    deadline: datetime | None = None
    deadline_unverified: bool = False
    certainty: Certainty
    decisions: list[Decision] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    reasons: list[dict] = Field(default_factory=list)   # filled by the ranker
    rank: int | None = None
    transfers: list[TransferCheck] = Field(default_factory=list)   # change-of-train checks
    worst_transfer: TransferClass | None = None
    changes: int = 0
    decision_leg: int = 1              # which leg of the journey the decisions are about

    @property
    def transfer_risk(self) -> int:
        return RISK_ORDER[self.worst_transfer] if self.worst_transfer else 0
