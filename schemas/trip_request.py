from pydantic import BaseModel, Field


class Travelers(BaseModel):
    adults: int = 1
    children: int = 0
    seniors: int = 0


class Budget(BaseModel):
    amount: float
    currency: str = "CNY"


class TripRequest(BaseModel):
    origin: str | None = Field(default=None, description="出发地")
    destination: str | None = Field(default=None, description="目的地")
    start_date: str | None = Field(default=None, description="出发日期")
    end_date: str | None = Field(default=None, description="结束日期")
    duration_days: int | None = Field(default=None, description="旅行天数")
    travelers: Travelers = Field(default_factory=Travelers)
    budget: Budget | None = None
    hotel_budget_per_night: float | None = Field(default=None, description="每晚酒店预算")
    interests: list[str] = Field(default_factory=list)
    pace: str = Field(default="normal", description="relaxed / normal / packed")
    special_requirements: list[str] = Field(default_factory=list)
