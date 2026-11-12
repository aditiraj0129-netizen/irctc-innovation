"""Data models for the rules engine.

Money is always stored in PAISE as an integer (₹1 = 100 paise).
We never use floats for money.
"""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.clock import ensure_aware


# ---------- Enums ----------

class TrainCategory(str, Enum):
    REGULAR = "REGULAR"
    VANDE_BHARAT_SLEEPER = "VANDE_BHARAT_SLEEPER"
    AMRIT_BHARAT_II = "AMRIT_BHARAT_II"


class TravelClass(str, Enum):
    FIRST_AC = "1A"
    EXEC_CHAIR = "EC"
    SECOND_AC = "2A"
    FIRST_CLASS = "FC"
    THIRD_AC = "3A"
    CHAIR_CAR = "CC"
    THIRD_AC_ECONOMY = "3E"
    SLEEPER = "SL"
    SECOND_SITTING = "2S"


AC_CLASSES = {
    TravelClass.FIRST_AC, TravelClass.EXEC_CHAIR, TravelClass.SECOND_AC,
    TravelClass.THIRD_AC, TravelClass.CHAIR_CAR, TravelClass.THIRD_AC_ECONOMY,
}


class Quota(str, Enum):
    GENERAL = "GENERAL"
    TATKAL = "TATKAL"


class TicketStatus(str, Enum):
    CONFIRMED = "CONFIRMED"
    RAC = "RAC"
    WAITLISTED = "WAITLISTED"


class LegalStatus(str, Enum):
    NOTIFIED = "NOTIFIED"      # in the Gazette / a Railway Board circular
    ANNOUNCED = "ANNOUNCED"    # announced by the Ministry, notification not found yet


class SlabType(str, Enum):
    FLAT = "FLAT"              # deduct the flat per-passenger charge
    PERCENT = "PERCENT"        # deduct a % of the fare
    NO_REFUND = "NO_REFUND"


class Outcome(str, Enum):
    REFUND_ON_CANCEL = "REFUND_ON_CANCEL"
    NO_REFUND = "NO_REFUND"
    AUTO_REFUND = "AUTO_REFUND"
    ELIGIBLE_TO_FILE_TDR = "ELIGIBLE_TO_FILE_TDR"
    NOT_ELIGIBLE = "NOT_ELIGIBLE"
    NEEDS_VERIFICATION = "NEEDS_VERIFICATION"
    NOT_MODELLED = "NOT_MODELLED"


# ---------- Rule data (loaded from rulesets.yaml) ----------

class Source(BaseModel):
    title: str
    url: str | None = None
    strength: str                      # e.g. "official", "media report"
    last_verified: date | None = None  # None = not yet checked by us
    note: str | None = None


class Slab(BaseModel):
    """One time window. Applies when hours_left > min_hours
    (or >= when min_inclusive). The last slab has min_hours = None."""
    min_hours: float | None
    min_inclusive: bool = True
    type: SlabType
    percent: int | None = None
    min_flat: bool = False

    @model_validator(mode="after")
    def check_percent(self) -> "Slab":
        if self.type == SlabType.PERCENT and not self.percent:
            raise ValueError("PERCENT slab needs a percent")
        return self


class RuleSet(BaseModel):
    id: str
    name: str
    train_categories: list[TrainCategory]
    effective_from: date
    effective_to: date | None = None
    legal_status: LegalStatus
    source: Source
    flat_charge_paise: dict[TravelClass, int]
    confirmed_slabs: list[Slab]
    clerkage_paise_per_passenger: int | None = None
    rac_wl_cancel_cutoff_minutes: int | None = None
    allowed_statuses: list[TicketStatus] = Field(default_factory=lambda: list(TicketStatus))
    allowed_quotas: list[Quota] = Field(default_factory=lambda: list(Quota))
    tatkal_confirmed_refund: bool = False

    @field_validator("confirmed_slabs")
    @classmethod
    def last_slab_is_open(cls, slabs: list[Slab]) -> list[Slab]:
        if not slabs or slabs[-1].min_hours is not None:
            raise ValueError("the last slab must have min_hours: null")
        bounds = [s.min_hours for s in slabs[:-1]]
        if bounds != sorted(bounds, reverse=True):
            raise ValueError("slabs must be ordered from most hours to least")
        return slabs


class SpecialRule(BaseModel):
    """TDR and automatic-refund rules."""
    id: str
    name: str
    train_categories: list[TrainCategory]
    effective_from: date
    effective_to: date | None = None
    legal_status: LegalStatus
    source: Source
    params: dict = Field(default_factory=dict)
    needs_verification: bool = False


class RuleRegistryData(BaseModel):
    version: str
    rule_sets: list[RuleSet]
    special_rules: list[SpecialRule]


# ---------- Inputs ----------

class Ticket(BaseModel):
    train_no: str = Field(pattern=r"^\d{5}$")
    train_category: TrainCategory
    travel_class: TravelClass
    quota: Quota = Quota.GENERAL
    status: TicketStatus
    is_eticket: bool = True
    scheduled_departure: datetime          # from the passenger's boarding station
    fare_per_passenger_paise: int = Field(gt=0)
    passengers: int = Field(ge=1, le=6)

    @field_validator("scheduled_departure")
    @classmethod
    def must_be_aware(cls, v: datetime) -> datetime:
        return ensure_aware(v, "scheduled_departure")

    @property
    def total_fare_paise(self) -> int:
        return self.fare_per_passenger_paise * self.passengers


# ---------- Output ----------

APPROVAL_NOTE = ("A TDR is a request. The refund is decided by the Zonal Railway "
                 "under the refund rules and is not guaranteed.")


class Decision(BaseModel):
    kind: str
    outcome: Outcome
    refund_paise: int = 0                 # refund now, or amount IF a TDR is approved
    deduction_paise: int = 0
    deadline: datetime | None = None
    deadline_moves_with_live_status: bool = False
    rule_ids: list[str] = Field(default_factory=list)
    rule_set_id: str | None = None
    legal_status: LegalStatus | None = None
    source_title: str | None = None
    source_url: str | None = None
    last_verified: date | None = None
    approval_note: str | None = None
    warnings: list[str] = Field(default_factory=list)
    reason_key: str                       # a stable code the UI turns into Hindi/English text
