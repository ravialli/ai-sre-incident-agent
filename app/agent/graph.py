from langgraph.graph import StateGraph, START, END

from app.agent.state import IncidentState
from app.agent.nodes import (
    collect_metrics,
    collect_logs,
    collect_traces,
    analyze_metrics,
)


builder = StateGraph(IncidentState)

builder.add_node(
    "collect_metrics",
    collect_metrics,
)

builder.add_node(
    "collect_logs",
    collect_logs,
)

builder.add_node(
    "collect_traces",
    collect_traces,
)

builder.add_node(
    "analyze_metrics",
    analyze_metrics,
)

builder.add_edge(
    START,
    "collect_metrics",
)

builder.add_edge(
    "collect_metrics",
    "collect_logs",
)

builder.add_edge(
    "collect_logs",
    "collect_traces",
)

builder.add_edge(
    "collect_traces",
    "analyze_metrics",
)

builder.add_edge(
    "analyze_metrics",
    END,
)

incident_graph = builder.compile()