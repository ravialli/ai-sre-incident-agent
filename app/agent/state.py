from typing import TypedDict, Annotated
import operator


class IncidentState(TypedDict, total=False):
    alert_name: str
    cluster: str
    service: str
    severity: str
    window_start: int
    window_end: int

    metrics: dict
    logs: dict
    traces: dict

    probable_cause: str
    confidence: float
    evidence: list[dict[str, str]]
    recommended_actions: list[str]
    telemetry_errors: Annotated[list[str], operator.add]