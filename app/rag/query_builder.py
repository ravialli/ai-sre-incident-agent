from typing import Any

from app.agent.state import IncidentState


MAX_TRACES_IN_QUERY = 3
MAX_SPANS_PER_TRACE = 5
MAX_LOGS_IN_QUERY = 5
DOMINANT_SPAN_RATIO = 0.80


def build_runbook_query(state: IncidentState) -> str:
    
    telemetry_errors = state.get("telemetry_errors", [])

    all_telemetry_unavailable = all(
        error in telemetry_errors
        for error in (
            "metrics_unavailable",
            "logs_unavailable",
            "traces_unavailable",
        )
    )
    if all_telemetry_unavailable:
        return ("Metrics, logs, and traces are all unavailable for the incident window.\n"
    "Telemetry collection or export may be incomplete or unavailable.\n"
    "Need guidance for investigating telemetry loss and observability pipeline failures.\n")

    parts: list[str] = [
        f"Alert: {state['alert_name']}",
        f"Service: {state['service']}",
        f"Severity: {state['severity']}",
    ]

    _add_metrics(parts, state.get("metrics"))
    _add_traces(parts, state.get("traces"))
    _add_logs(parts, state.get("logs"))
    _add_telemetry_errors(parts, state.get("telemetry_errors"))

    return "\n".join(parts)

def _add_logs(parts: list[str], logs: Any) -> None:
    if not isinstance(logs, dict):
        return

    entries = logs.get("entries")

    if not isinstance(entries, list) or not entries:
        return

    parts.append("\nLogs:")
    count = 0

    for entry in entries:
        if not isinstance(entry, dict):
            continue

        message = entry.get("message")

        if not message:
            continue

        parts.append(f"- {message}")
        count += 1

        if count >= MAX_LOGS_IN_QUERY:
            break

def _add_metrics(parts: list[str], metrics: dict[str, Any] | None) -> None:
    if not metrics:
        return

    parts.append("\nMetrics:")

    p95_latency_ms = metrics.get("p95_latency_ms")
    p99_latency_ms = metrics.get("p99_latency_ms")

    p95_is_bucket_ceiling = metrics.get("p95_is_bucket_ceiling", False)
    p99_is_bucket_ceiling = metrics.get("p99_is_bucket_ceiling", False)

    # Keep retrieval wording semantic instead of dumping raw metric values.
    if p95_latency_ms is not None or p99_latency_ms is not None:
        if p95_is_bucket_ceiling or p99_is_bucket_ceiling:
            parts.append("Service latency reached the upper histogram bucket ceiling, so the true latency may be higher than the reported bucket value.")
        else:
            parts.append("Service latency is elevated.")

    error_rate = metrics.get("error_rate")

    if error_rate is not None:
        if error_rate == 0:
            parts.append("No errors were observed in the retrieved error-rate metric.")
        else:
            parts.append("Errors were observed in the retrieved error-rate metric.")

def _add_traces(parts: list[str], traces: Any) -> None:
    trace_items = _extract_trace_items(traces)

    if not trace_items:
        return

    parts.append("\nTrace evidence:")

    for index, trace in enumerate(trace_items[:MAX_TRACES_IN_QUERY], start=1):
        duration_ms = trace.get("duration_ms")
        window_relation = trace.get("window_relation")

        if duration_ms is not None:
            duration_seconds = duration_ms / 1000

            parts.append(f"Trace {index} took approximately {duration_seconds:.1f} seconds.")

        if window_relation:
            parts.append(_describe_window_relation(window_relation))

        spans = _extract_spans(trace)

        if not spans:
            continue
        
        diagnostic_spans = _select_diagnostic_spans(spans, duration_ms)

        for span in diagnostic_spans[:MAX_SPANS_PER_TRACE]:
            span_name = span.get("name")
            service = span.get("service")
            span_duration_ms = span.get("duration_ms")
            status = span.get("status")

            if not span_name:
                continue

            observations: list[str] = []

            if (duration_ms and isinstance(span_duration_ms, (int, float)) and duration_ms > 0):
                duration_ratio = span_duration_ms / duration_ms

                if duration_ratio >= DOMINANT_SPAN_RATIO:
                    observations.append(f"The {span_name} span consumed nearly all of the trace duration")
                else:
                    observations.append(f"The {span_name} span took approximately {span_duration_ms / 1000:.1f} seconds")
            elif isinstance(span_duration_ms, (int, float)):
                observations.append(f"The {span_name} span took approximately {span_duration_ms / 1000:.1f} seconds")
            else:
                observations.append(f"The trace contains a {span_name} span")

            if service:
                observations.append(f"service={service}")

            if status:
                observations.append(f"status={status}")

            parts.append("- " + ", ".join(observations) + ".")
            
def _describe_window_relation(window_relation: str) -> str:
    mappings = {
        "within_window":
            "The trace occurred within the incident window.",
        "overlaps_window_start":
            "The trace overlaps the start of the incident window.",
        "overlaps_window_end":
            "The trace overlaps the end of the incident window.",
        "spans_entire_window":
            "The trace spans the entire incident window.",
        "before_window":
            "The trace occurred before the incident window.",
        "after_window":
            "The trace occurred after the incident window.",
        "unknown":
            "The trace timing relative to the incident window is unknown.",
    }

    return mappings.get(window_relation, f"Trace window relation: {window_relation}.")

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

def _select_diagnostic_spans(spans: list[dict[str, Any]], trace_duration_ms: float | int | None) -> list[dict[str, Any]]:
    if not trace_duration_ms or trace_duration_ms <= 0:
        return _select_longest_spans(spans)

    dominant_spans = [span for span in spans if isinstance(span.get("duration_ms"), (int, float))
        and span["duration_ms"] / trace_duration_ms >= DOMINANT_SPAN_RATIO]

    if not dominant_spans:
        return _select_longest_spans(spans)

    parent_ids = {span.get("parent_span_id") for span in dominant_spans if span.get("parent_span_id")}

    deepest_dominant_spans = [span for span in dominant_spans
        if span.get("span_id") not in parent_ids]

    return deepest_dominant_spans or dominant_spans

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