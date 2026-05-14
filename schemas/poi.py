from pydantic import BaseModel, Field


class Poi(BaseModel):
    name: str
    city: str
    country: str = ""
    category: str = Field(description="attraction / food / shopping / rest")
    area: str
    tags: list[str] = Field(default_factory=list)
    rating: float = 4.0
    price_level: int = 1
    recommended_duration_minutes: int = 60
    address: str | None = None
    source: str = "local_sample"
