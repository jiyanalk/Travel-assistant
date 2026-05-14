try:
    from langchain.tools import tool
except ImportError:
    tool = None  # type: ignore[assignment]

from services.route_service import estimate_route


def estimate_route_time(area_from: str, area_to: str) -> dict:
    """Estimate travel duration between two areas with MVP local rules."""
    return estimate_route(area_from=area_from, area_to=area_to)


estimate_route_time_tool = tool(estimate_route_time) if tool else estimate_route_time
