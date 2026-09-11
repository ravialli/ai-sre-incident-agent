from typing import Any

from app.agent.state import IncidentState
from app.rag.retriever import retrieve_runbooks


MAX_TRACES_IN_QUERY = 3
MAX_SPANS_PER_TRACE = 5


def build_runbook_query(state: IncidentState) -> str:
    parts: list[str] = [
        f"Alert: {state['alert_name']}",
        f"Service: {state['service']}",
        f"Severity: {state['severity']}",
    ]

    _add_metrics(parts, state.get("metrics"))
    _add_traces(parts, state.get("traces"))
    _add_telemetry_errors(parts, state.get("telemetry_errors"))

    return "\n".join(parts)


def _add_metrics(parts: list[str], metrics: dict[str, Any] | None) -> None:
    if not metrics:
        return

    parts.append("\nMetrics:")

    protocol = metrics.get("protocol")
    if protocol:
        parts.append(f"Protocol: {protocol}")

    request_rate = metrics.get("request_rate")
    if request_rate is not None:
        parts.append(f"Request rate: {request_rate}")

    error_rate = metrics.get("error_rate")
    if error_rate is not None:
        parts.append(f"Error rate: {error_rate}")

    p95_latency_ms = metrics.get("p95_latency_ms")
    p95_is_bucket_ceiling = metrics.get("p95_is_bucket_ceiling", False)

    if p95_latency_ms is not None:
        if p95_is_bucket_ceiling:
            parts.append(f"P95 latency reached the {p95_latency_ms} ms histogram bucket ceiling")
        else:
            parts.append(f"P95 latency: {p95_latency_ms} ms")

    p99_latency_ms = metrics.get("p99_latency_ms")
    p99_is_bucket_ceiling = metrics.get("p99_is_bucket_ceiling", False)

    if p99_latency_ms is not None:
        if p99_is_bucket_ceiling:
            parts.append(f"P99 latency reached the {p99_latency_ms} ms histogram bucket ceiling")
        else:
            parts.append(f"P99 latency: {p99_latency_ms} ms")


def _add_traces(parts: list[str], traces: Any) -> None:
    trace_items = _extract_trace_items(traces)

    if not trace_items:
        return

    parts.append("\nTraces:")

    for index, trace in enumerate(trace_items[:MAX_TRACES_IN_QUERY],start=1):
        trace_id = trace.get("trace_id") or trace.get("traceID")
        duration_ms = trace.get("duration_ms")
        window_relation = trace.get("window_relation")

        trace_parts: list[str] = [f"Trace {index}"]

        if trace_id:
            trace_parts.append(f"id={trace_id}")

        if duration_ms is not None:
            trace_parts.append(f"duration={duration_ms} ms")

        if window_relation:
            trace_parts.append(f"window_relation={window_relation}")

        parts.append(", ".join(trace_parts))

        spans = _extract_spans(trace)

        if not spans:
            continue

        longest_spans = _select_longest_spans(spans)

        for span in longest_spans[:MAX_SPANS_PER_TRACE]:
            span_name = span.get("name")
            service = span.get("service")
            span_duration_ms = span.get("duration_ms")
            status = span.get("status")

            observations: list[str] = []

            if span_name:
                observations.append(f"span={span_name}")

            if service:
                observations.append(f"service={service}")

            if span_duration_ms is not None:
                observations.append(f"duration={span_duration_ms} ms")

            if status:
                observations.append(f"status={status}")

            if observations:
                parts.append("- " + ", ".join(observations))


def _extract_trace_items(traces: Any) -> list[dict[str, Any]]:
    if not traces:
        return []

    if isinstance(traces, list):
        return [trace for trace in traces if isinstance(trace, dict)]

    if not isinstance(traces, dict):
        return []

    for key in ("traces", "results", "entries", "items"):
        value = traces.get(key)

        if isinstance(value, list):
            return [trace for trace in value if isinstance(trace, dict)]

    return []


def _extract_spans(trace: dict[str, Any]) -> list[dict[str, Any]]:
    spans = trace.get("spans")

    if isinstance(spans, list):
        return [span for span in spans if isinstance(span, dict)]

    details = trace.get("details")

    if isinstance(details, dict):
        spans = details.get("spans")

        if isinstance(spans, list):
            return [span for span in spans if isinstance(span, dict)]

    return []


def _select_longest_spans(spans: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(spans, key=lambda span: (span.get("duration_ms") if isinstance(span.get("duration_ms"), (int, float)) else 0), reverse=True)


def _add_telemetry_errors(parts: list[str], telemetry_errors: list[str] | None) -> None:
    if not telemetry_errors:
        return

    parts.append("\nTelemetry availability:")

    for error in telemetry_errors:
        parts.append(f"- {_humanize_telemetry_error(error)}")


def _humanize_telemetry_error(error: str) -> str:
    mappings = {
        "metrics_unavailable":
            "Metrics telemetry unavailable",
        "logs_unavailable":
            "Logs telemetry unavailable",
        "traces_unavailable":
            "Trace telemetry unavailable",
    }

    return mappings.get(error, error.replace("_", " "))
    