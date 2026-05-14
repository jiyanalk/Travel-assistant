from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db
from repositories.user_repository import UserRepository
from schemas.user_profile import UserProfile


router = APIRouter()


@router.get("/{user_id}/profile", response_model=UserProfile)
def get_user_profile(user_id: str, db: Session = Depends(get_db)) -> UserProfile:
    profile = UserRepository(db).get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="User profile not found.")
    return profile
