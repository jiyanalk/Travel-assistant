try:
    from langchain.tools import tool
except ImportError:
    tool = None  # type: ignore[assignment]

from services.poi_service import search_candidate_pois


def search_pois(destination: str, interests: list[str], limit: int = 30) -> list[dict]:
    """Search candidate POIs from local sample data."""
    return search_candidate_pois(destination=destination, interests=interests, limit=limit)


search_pois_tool = tool(search_pois) if tool else search_pois
