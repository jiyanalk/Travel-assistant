from langgraph.graph import END, START, StateGraph

from graphs.nodes import (
    ask_clarification,
    build_daily_itinerary,
    check_missing_fields,
    estimate_routes_and_budget,
    format_trip_plan,
    load_user_memory,
    parse_user_request,
    prepare_destination_context,
    rank_and_cluster_pois,
    save_memory,
    validate_itinerary,
)
from graphs.state import TravelState


def should_ask_clarification(state: TravelState) -> str:
    if state.get("missing_fields"):
        return "ask_clarification"
    return "load_user_memory"


def build_travel_graph():
    graph = StateGraph(TravelState)

    graph.add_node("parse_user_request", parse_user_request)
    graph.add_node("check_missing_fields", check_missing_fields)
    graph.add_node("ask_clarification", ask_clarification)
    graph.add_node("load_user_memory", load_user_memory)
    graph.add_node("prepare_destination_context", prepare_destination_context)
    graph.add_node("rank_and_cluster_pois", rank_and_cluster_pois)
    graph.add_node("build_daily_itinerary", build_daily_itinerary)
    graph.add_node("estimate_routes_and_budget", estimate_routes_and_budget)
    graph.add_node("validate_itinerary", validate_itinerary)
    graph.add_node("format_trip_plan", format_trip_plan)
    graph.add_node("save_memory", save_memory)

    graph.add_edge(START, "parse_user_request")
    graph.add_edge("parse_user_request", "check_missing_fields")
    graph.add_conditional_edges(
        "check_missing_fields",
        should_ask_clarification,
        {
            "ask_clarification": "ask_clarification",
            "load_user_memory": "load_user_memory",
        },
    )
    graph.add_edge("ask_clarification", END)
    graph.add_edge("load_user_memory", "prepare_destination_context")
    graph.add_edge("prepare_destination_context", "rank_and_cluster_pois")
    graph.add_edge("rank_and_cluster_pois", "build_daily_itinerary")
    graph.add_edge("build_daily_itinerary", "estimate_routes_and_budget")
    graph.add_edge("estimate_routes_and_budget", "validate_itinerary")
    graph.add_edge("validate_itinerary", "format_trip_plan")
    graph.add_edge("format_trip_plan", "save_memory")
    graph.add_edge("save_memory", END)
    return graph.compile()
