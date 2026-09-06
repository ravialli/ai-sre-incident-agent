from typing import TypedDict


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
    evidence: list[str]
    recommended_actions: list[str]