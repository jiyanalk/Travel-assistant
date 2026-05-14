import uuid
from datetime import datetime

from sqlalchemy.orm import Session

from db.models import TripModel
from schemas.trip_plan import TripPlan
from schemas.trip_request import TripRequest


class TripRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_trip(self, user_id: str, request: TripRequest | None, trip_plan: TripPlan) -> TripModel:
        trip = TripModel(
            id=str(uuid.uuid4()),
            user_id=user_id,
            origin=request.origin if request else None,
            destination=trip_plan.destination,
            start_date=request.start_date if request else None,
            end_date=request.end_date if request else None,
            duration_days=trip_plan.duration_days,
            travelers_json=request.travelers.model_dump() if request else {},
            budget_json=request.budget.model_dump() if request and request.budget else {},
            interests_json=request.interests if request else [],
            pace=request.pace if request else "normal",
            trip_plan_json=trip_plan.model_dump(),
            status="planned",
            created_at=datetime.utcnow().isoformat(),
            updated_at=datetime.utcnow().isoformat(),
        )
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        return trip

    def get_by_id(self, trip_id: str) -> TripModel | None:
        return self.db.query(TripModel).filter(TripModel.id == trip_id).first()

    def update_trip_plan(self, trip_id: str, trip_plan: TripPlan) -> TripModel | None:
        trip = self.get_by_id(trip_id)
        if trip is None:
            return None
        trip.trip_plan_json = trip_plan.model_dump()
        trip.updated_at = datetime.utcnow().isoformat()
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        return trip

    def build_trip_request_from_model(self, trip: TripModel) -> TripRequest:
        payload = {
            "origin": trip.origin,
            "destination": trip.destination,
            "start_date": trip.start_date,
            "end_date": trip.end_date,
            "duration_days": trip.duration_days,
            "travelers": trip.travelers_json or {},
            "budget": trip.budget_json or None,
            "interests": trip.interests_json or [],
            "pace": trip.pace or "normal",
        }
        return TripRequest.model_validate(payload)
