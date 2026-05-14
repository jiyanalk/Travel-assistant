try:
    from langchain.tools import tool
except ImportError:
    tool = None  # type: ignore[assignment]

from services.rag_service import retrieve_guide_context


def search_travel_guides(destination: str, interests: list[str], pace: str) -> list[str]:
    """Retrieve local guide snippets relevant to the destination."""
    return retrieve_guide_context(destination=destination, interests=interests, pace=pace)


search_travel_guides_tool = tool(search_travel_guides) if tool else search_travel_guides
