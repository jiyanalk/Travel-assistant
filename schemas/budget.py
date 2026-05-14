from pydantic import BaseModel, Field


class HotelRecommendation(BaseModel):
    name: str
    area: str
    nightly_price: float
    rating: float | None = None
    reason: str | None = None
    booking_hint: str | None = None
    is_estimated: bool = True
    source: str = "local_sample"


class TripBudget(BaseModel):
    currency: str = "CNY"
    user_budget: float | None = None
    hotel_budget_per_night: float | None = None
    estimated_total: float
    hotel_total: float = 0
    status: str
    hotel_recommendations: list[HotelRecommendation] = Field(default_factory=list)
    is_estimated: bool = True
