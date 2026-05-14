from sqlalchemy import JSON, Column, Float, Integer, String
from sqlalchemy.orm import declarative_base


Base = declarative_base()


class TripModel(Base):
    __tablename__ = "trips"

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=True)
    origin = Column(String, nullable=True)
    destination = Column(String, nullable=False)
    start_date = Column(String, nullable=True)
    end_date = Column(String, nullable=True)
    duration_days = Column(Integer, nullable=False)
    travelers_json = Column(JSON, nullable=True)
    budget_json = Column(JSON, nullable=True)
    interests_json = Column(JSON, nullable=True)
    pace = Column(String, nullable=True)
    trip_plan_json = Column(JSON, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(String, nullable=True)
    updated_at = Column(String, nullable=True)


class UserProfileModel(Base):
    __tablename__ = "user_profiles"

    user_id = Column(String, primary_key=True)
    home_city = Column(String, nullable=True)
    budget_preference = Column(String, nullable=True)
    pace_preference = Column(String, nullable=True)
    interests_json = Column(JSON, nullable=True)
    food_preference_json = Column(JSON, nullable=True)
    disliked_tags_json = Column(JSON, nullable=True)
    updated_at = Column(String, nullable=True)


class PoiModel(Base):
    __tablename__ = "pois"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    country = Column(String, nullable=True)
    category = Column(String, nullable=False)
    area = Column(String, nullable=False)
    tags_json = Column(JSON, nullable=True)
    rating = Column(Float, nullable=True)
    price_level = Column(Integer, nullable=True)
    recommended_duration_minutes = Column(Integer, nullable=True)
    address = Column(String, nullable=True)
    source = Column(String, nullable=True)
    updated_at = Column(String, nullable=True)
