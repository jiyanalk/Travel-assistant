from sqlalchemy import JSON, Column, String
from sqlalchemy.orm import declarative_base


Base = declarative_base()


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
