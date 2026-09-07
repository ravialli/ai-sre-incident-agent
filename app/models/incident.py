from pydantic import BaseModel, Field


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
    probable_cause: str = Field(
        description="Most likely cause supported by the supplied incident evidence. Do not invent unsupported causes."
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that the probable cause is supported by the available evidence."
    )

    evidence: list[str] = Field(
        description="Specific observations from metrics, logs, or traces that support the analysis."
    )

    recommended_actions: list[str] = Field(
        description="Read-only investigation or remediation recommendations. Do not perform infrastructure changes."
    )