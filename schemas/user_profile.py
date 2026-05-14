from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    user_id: str
    home_city: str | None = None
    budget_preference: str | None = None
    pace_preference: str | None = None
    interests: list[str] = Field(default_factory=list)
    food_preferences: list[str] = Field(default_factory=list)
    disliked_tags: list[str] = Field(default_factory=list)
    history_destinations: list[str] = Field(default_factory=list)
