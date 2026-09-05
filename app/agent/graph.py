from langgraph.graph import StateGraph, START, END

from app.agent.state import IncidentState
from app.agent.nodes import collect_metrics


builder = StateGraph(IncidentState)

builder.add_node(
    "collect_metrics",
    collect_metrics
)

builder.add_edge(
    START,
    "collect_metrics"
)

builder.add_edge(
    "collect_metrics",
    END
)

incident_graph = builder.compile()