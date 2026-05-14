from __future__ import annotations

import uuid
from typing import Any, Callable

from sqlalchemy.orm import Session

from graphs.state import TravelState
from graphs.travel_graph import build_travel_graph
from repositories.trip_repository import TripRepository
from schemas.api import TripDetailResponse, TripPlanResponse
from schemas.trip_plan import TripPlan
from services.itinerary_service import revise_trip_plan_from_message
from services.thread_service import clear_thread_message, load_thread_message, save_thread_message


EventEmitter = Callable[[dict[str, Any]], None]


class TravelPlanningAgent:
    def __init__(self, db: Session):
        self.db = db
        self.graph = build_travel_graph()
        self.trip_repository = TripRepository(db)

    def plan_trip(
        self,
        message: str,
        user_id: str | None = None,
        thread_id: str | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> TripPlanResponse:
        resolved_thread_id = thread_id or f"trip_thread_{uuid.uuid4().hex[:8]}"
        resolved_user_id = user_id or "guest"
        previous_message = load_thread_message(resolved_thread_id) if thread_id else None
        combined_message = f"{previous_message}\n{message}".strip() if previous_message else message

        initial_state: TravelState = {
            "user_id": resolved_user_id,
            "thread_id": resolved_thread_id,
            "user_message": combined_message,
            "agent_steps": [],
            "event_emitter": event_emitter,
        }
        result = self.graph.invoke(initial_state)

        trip_plan = result.get("formatted_trip_plan")
        need_clarification = bool(result.get("need_clarification"))
        clarification_question = result.get("clarification_question")
        trip_id: str | None = None

        if trip_plan is not None:
            trip = self.trip_repository.save_trip(
                user_id=result["user_id"],
                request=result.get("trip_request"),
                trip_plan=trip_plan,
            )
            trip_id = trip.id
            clear_thread_message(resolved_thread_id)
        elif need_clarification:
            save_thread_message(
                thread_id=resolved_thread_id,
                user_id=resolved_user_id,
                message=combined_message,
            )

        response = TripPlanResponse(
            trip_id=trip_id,
            thread_id=result.get("thread_id", resolved_thread_id),
            need_clarification=need_clarification,
            clarification_question=clarification_question,
            trip_request=result.get("trip_request"),
            trip_plan=trip_plan,
            agent_steps=result.get("agent_steps", []),
        )
        if event_emitter is not None:
            event_emitter(
                {
                    "type": "plan_result",
                    "payload": response.model_dump(mode="json"),
                }
            )
        return response

    def revise_trip_plan(
        self,
        *,
        trip_plan: TripPlan,
        message: str,
        trip_id: str | None = None,
        event_emitter: EventEmitter | None = None,
    ) -> tuple[TripPlan, list[str]]:
        if event_emitter is not None:
            event_emitter({"type": "step_start", "step": "revise_trip_plan"})
        updated_plan, changes = revise_trip_plan_from_message(
            current_plan=trip_plan,
            message=message,
        )
        if trip_id:
            self.trip_repository.update_trip_plan(trip_id=trip_id, trip_plan=updated_plan)
        return updated_plan, changes

    def get_trip(self, trip_id: str) -> TripDetailResponse | None:
        trip = self.trip_repository.get_by_id(trip_id)
        if trip is None or not trip.trip_plan_json:
            return None

        return TripDetailResponse(
            trip_id=trip.id,
            user_id=trip.user_id,
            status=trip.status,
            trip_request=self.trip_repository.build_trip_request_from_model(trip),
            trip_plan=TripPlan.model_validate(trip.trip_plan_json),
        )
