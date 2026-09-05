from pydantic import BaseModel


class IncidentInput(BaseModel):
    alert_name: str
    cluster: str
    service: str
    severity: str


class ServiceMetrics(BaseModel):
    service: str
    request_rate: float
    error_rate: float
    p95_latency: float
    p99_latency: float


class IncidentAnalysis(BaseModel):
    probable_cause: str
    confidence: float
    evidence: list[str]
    recommended_actions: list[str]