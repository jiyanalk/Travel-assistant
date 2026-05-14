try:
    from langchain.tools import tool
except ImportError:
    tool = None  # type: ignore[assignment]

from schemas.trip_request import Budget, TripRequest, Travelers
from services.budget_service import build_budget


def estimate_budget(
    destination: str,
    duration_days: int,
    travelers_count: int,
    pace: str,
    user_budget: float | None = None,
) -> dict:
    """Estimate trip budget using local rules for the MVP."""
    request = TripRequest(
        destination=destination,
        duration_days=duration_days,
        travelers=Travelers(adults=travelers_count),
        pace=pace,
    )
    if user_budget is not None:
        request.budget = Budget(amount=user_budget, currency="CNY")
    return build_budget(
        request=request,
        draft_plan={"days": []},
        user_budget=user_budget,
    )


estimate_budget_tool = tool(estimate_budget) if tool else estimate_budget
