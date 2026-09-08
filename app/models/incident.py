from pydantic import BaseModel, Field
from typing import Literal


class IncidentInput(BaseModel):
    alert_name: str
    cluster: str
    service: str
    severity: str


class ServiceMetrics(BaseModel):
    service: str
    protocol: str
    request_rate: float | None
    error_rate: float | None
    p95_latency_ms: float | None
    p99_latency_ms: float | None

class EvidenceItem(BaseModel):
    source: Literal["metrics", "logs", "traces"]
    observation: str


class IncidentAnalysis(BaseModel):
    probable_cause: str = Field(
        description="Most likely cause supported by the supplied incident evidence. Do not invent unsupported causes."
    )

    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence that the probable cause is supported by the available evidence."
    )

    evidence: list[EvidenceItem] = Field(
        description="Concrete observations from the supplied incident telemetry. Each item must identify its telemetry source and must not contain unsupported facts."
    )

    recommended_actions: list[str] = Field(
        description="Read-only investigation or remediation recommendations. Do not perform infrastructure changes."
    )