from pydantic import BaseModel, Field

from schemas.budget import TripBudget


class TransportInfo(BaseModel):
    mode: str
    duration_minutes: int | None = None
    distance_km: float | None = None
    estimated_cost: float | None = None
    description: str | None = None
    is_estimated: bool = True


class TripItem(BaseModel):
    time: str
    type: str = Field(description="transport / attraction / food / rest / shopping")
    title: str
    location: str | None = None
    duration_minutes: int | None = None
    estimated_cost: float | None = None
    is_cost_estimated: bool = True
    reason: str | None = None
    notes: str | None = None
    transport_to_next: TransportInfo | None = None


class DayPlan(BaseModel):
    day: int
    date: str | None = None
    theme: str
    pace: str
    items: list[TripItem]
    estimated_cost: float
    transport_summary: str | None = None
    backup_plan: str | None = None


class TripPlan(BaseModel):
    trip_title: str
    destination: str
    duration_days: int
    travel_style: list[str]
    summary: str
    days: list[DayPlan]
    budget: TripBudget
    backup_plans: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
