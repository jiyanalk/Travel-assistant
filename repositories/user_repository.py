from sqlalchemy.orm import Session

from db.models import UserProfileModel
from schemas.user_profile import UserProfile


class UserRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_profile(self, user_id: str) -> UserProfile | None:
        row = self.db.query(UserProfileModel).filter(UserProfileModel.user_id == user_id).first()
        if row is None:
            return None
        return UserProfile(
            user_id=row.user_id,
            home_city=row.home_city,
            budget_preference=row.budget_preference,
            pace_preference=row.pace_preference,
            interests=row.interests_json or [],
            food_preferences=row.food_preference_json or [],
            disliked_tags=row.disliked_tags_json or [],
        )
