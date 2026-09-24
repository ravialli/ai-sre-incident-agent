from app.agent.state import IncidentState
from app.tools.metrics import MetricsTool
from app.tools.logs import LogsTool
from app.tools.traces import TraceTool
import asyncio
from langchain.messages import SystemMessage
import logging
from app.rag.query_builder import build_runbook_query
from app.rag.retriever import retrieve_runbooks

logger = logging.getLogger(__name__)

from app.agent.llm import get_incident_analysis_model
from app.agent.prompts import (INCIDENT_SYSTEM_PROMPT, build_incident_message)


async def collect_metrics(state: dict) -> dict:
    metrics_tool = MetricsTool()
    try:
        metrics = await metrics_tool.get_service_metrics(state["service"], time=state["window_end"])
        return {"metrics": metrics}
    except Exception:
        logger.exception("Metrics collection failed for service = %s", state.get("service"))
        return {"metrics": {}, "telemetry_errors": ["metrics_unavailable"]}
        
async def collect_logs(state: dict) -> dict:
    logs_tool = LogsTool()
    try:
        logs = await logs_tool.get_service_logs(state["service"], start=state["window_start"], end=state["window_end"])
        return {"logs": logs}
    except Exception:
        logger.exception("Logs collection failed for service = %s", state.get("service"))
        return {"logs": {}, "telemetry_errors": ["logs_unavailable"]}
    
def _rank_trace_ids_from_logs(logs: dict, limit: int = 3) -> list[dict]:
    """
    Rank trace IDs using the time span between their earliest and latest
    checkout log entries.

    This is only a trace-selection signal. It is not treated as the
    authoritative trace duration.
    """
    entries = logs.get("entries") or []

    grouped: dict[str, list[int]] = {}

    for entry in entries:
        labels = entry.get("labels") or {}
        trace_id = labels.get("trace_id")
        timestamp = entry.get("timestamp")

        if not trace_id or timestamp is None:
            continue

        try:
            timestamp_ns = int(timestamp)
        except (TypeError, ValueError):
            continue

        grouped.setdefault(trace_id, []).append(timestamp_ns)

    candidates = []

    for trace_id, timestamps in grouped.items():
        earliest = min(timestamps)
        latest = max(timestamps)

        candidates.append(
            {
                "trace_id": trace_id,
                "log_span_ms": (latest - earliest) / 1_000_000,
                "log_entries": len(timestamps),
                "selection_source": "loki_log_correlation",
            }
        )

    candidates.sort(
        key=lambda candidate: (
            candidate["log_span_ms"],
            candidate["log_entries"],
        ),
        reverse=True,
    )

    return candidates[:limit]
    
async def collect_traces(state: dict) -> dict:
    trace_tool = TraceTool()

    try:
        trace_result = await trace_tool.get_service_traces(
            state["service"],
            start=state["window_start"],
            end=state["window_end"],
        )

        trace_summaries = trace_result.get("traces") or []

        summaries_by_id = {
            trace["trace_id"]: trace
            for trace in trace_summaries
            if trace.get("trace_id")
        }

        candidates_with_ids = []
        selected_ids = set()

        # 1. Prefer traces that look suspicious based on correlated Loki logs.
        log_candidates = _rank_trace_ids_from_logs(
            state.get("logs") or {},
            limit=3,
        )

        for log_candidate in log_candidates:
            trace_id = log_candidate["trace_id"]

            existing_summary = summaries_by_id.get(trace_id)

            if existing_summary:
                candidate = dict(existing_summary)
            else:
                candidate = {
                    "trace_id": trace_id,
                    "root_service": state.get("service"),
                }

            candidate.update(
                {
                    "selection_source": "loki_log_correlation",
                    "log_span_ms": log_candidate["log_span_ms"],
                    "log_entries": log_candidate["log_entries"],
                }
            )

            candidates_with_ids.append(candidate)
            selected_ids.add(trace_id)

            if len(candidates_with_ids) == 3:
                break

        # 2. If logs did not give us three candidates,
        #    fill the remaining slots using the longest Tempo search results.
        if len(candidates_with_ids) < 3:
            remaining_traces = sorted(
                trace_summaries,
                key=lambda trace: float(trace.get("duration_ms") or 0),
                reverse=True,
            )

            for trace in remaining_traces:
                trace_id = trace.get("trace_id")

                if not trace_id or trace_id in selected_ids:
                    continue

                candidate = dict(trace)
                candidate["selection_source"] = "tempo_duration"

                candidates_with_ids.append(candidate)
                selected_ids.add(trace_id)

                if len(candidates_with_ids) == 3:
                    break

        # 3. Fetch full trace details concurrently.
        tasks = [
            trace_tool.get_trace_details(trace_id=trace["trace_id"])
            for trace in candidates_with_ids
        ]

        trace_details = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        for trace, details in zip(candidates_with_ids, trace_details):
            if isinstance(details, Exception):
                logger.warning(
                    "Trace detail retrieval failed for trace_id=%s: %s",
                    trace.get("trace_id"),
                    details,
                )
                trace["details_error"] = "trace_details_unavailable"
                continue

            trace["details"] = details

        # Put the diagnostically selected traces first.
        # Your query builder only inspects a bounded number of traces,
        # so ordering matters.
        remaining = [
            trace
            for trace in trace_summaries
            if trace.get("trace_id") not in selected_ids
        ]

        trace_result["traces"] = candidates_with_ids + remaining

        return {"traces": trace_result}

    except Exception:
        logger.exception(
            "Traces collection failed for service=%s",
            state.get("service"),
        )
        return {
            "traces": {},
            "telemetry_errors": ["traces_unavailable"],
        }

def _find_dominant_downstream_service(
    traces: dict,
    alerted_service: str,
) -> dict | None:
    """
    Find a downstream service whose span dominates an alerted-service span.

    Only considers service-boundary transitions where a span from another
    service is a child of a span owned by the alerted service.
    """

    trace_entries = traces.get("traces") or []
    candidates = []

    # The first traces are our diagnostically selected traces.
    for trace in trace_entries[:3]:
        details = trace.get("details") or {}
        spans = details.get("spans") or []

        spans_by_id = {
            span["span_id"]: span
            for span in spans
            if span.get("span_id")
        }

        for span in spans:
            service = span.get("service")
            parent_span_id = span.get("parent_span_id")
            duration_ms = span.get("duration_ms")

            if (
                not service
                or service == alerted_service
                or not parent_span_id
                or duration_ms is None
            ):
                continue

            parent = spans_by_id.get(parent_span_id)

            if not parent:
                continue

            # We only want a real service-boundary transition:
            #
            # checkout span
            #     ↓
            # shipping span
            if parent.get("service") != alerted_service:
                continue

            parent_duration_ms = parent.get("duration_ms")

            duration_ratio = None

            if parent_duration_ms and parent_duration_ms > 0:
                duration_ratio = duration_ms / parent_duration_ms

            candidates.append(
                {
                    "service": service,
                    "trace_id": trace.get("trace_id"),
                    "span_name": span.get("name"),
                    "duration_ms": duration_ms,
                    "parent_span_name": parent.get("name"),
                    "parent_duration_ms": parent_duration_ms,
                    "duration_ratio": duration_ratio,
                }
            )

    if not candidates:
        return None

    # Prefer the downstream span consuming the most time.
    candidates.sort(
        key=lambda candidate: candidate["duration_ms"],
        reverse=True,
    )

    return candidates[0]


async def identify_downstream_service(state: dict) -> dict:
    candidate = _find_dominant_downstream_service(
        traces=state.get("traces") or {},
        alerted_service=state["service"],
    )

    if not candidate:
        return {
            "downstream_service": None,
            "downstream_selection": {},
        }

    # Avoid expanding tiny downstream calls.
    duration_ms = candidate.get("duration_ms") or 0
    duration_ratio = candidate.get("duration_ratio") or 0

    if duration_ms < 500 or duration_ratio < 0.5:
        return {
            "downstream_service": None,
            "downstream_selection": {},
        }

    return {
        "downstream_service": candidate["service"],
        "downstream_selection": candidate,
    }
    

async def collect_downstream_telemetry(state: dict) -> dict:
    service = state.get("downstream_service")

    if not service:
        return {
            "downstream_telemetry": {},
            "downstream_telemetry_errors": [],
        }

    metrics_tool = MetricsTool()
    logs_tool = LogsTool()
    trace_tool = TraceTool()

    errors = []

    metrics = {}
    logs = {}
    traces = {}

    # Metrics
    try:
        metrics = await metrics_tool.get_service_metrics(
            service,
            time=state["window_end"],
        )
    except Exception:
        logger.exception(
            "Downstream metrics collection failed for service=%s",
            service,
        )
        errors.append("downstream_metrics_unavailable")

    # Logs
    try:
        logs = await logs_tool.get_service_logs(
            service,
            start=state["window_start"],
            end=state["window_end"],
        )
    except Exception:
        logger.exception(
            "Downstream logs collection failed for service=%s",
            service,
        )
        errors.append("downstream_logs_unavailable")

    # Traces
    try:
        trace_result = await trace_tool.get_service_traces(
            service,
            start=state["window_start"],
            end=state["window_end"],
        )

        trace_summaries = trace_result.get("traces") or []

        # For downstream exploration, longest traces are most useful.
        candidates = sorted(
            [
                trace
                for trace in trace_summaries
                if trace.get("trace_id")
            ],
            key=lambda trace: float(
                trace.get("duration_ms") or 0
            ),
            reverse=True,
        )[:3]

        detail_tasks = [
            trace_tool.get_trace_details(
                trace_id=trace["trace_id"]
            )
            for trace in candidates
        ]

        details = await asyncio.gather(
            *detail_tasks,
            return_exceptions=True,
        )

        for trace, detail in zip(candidates, details):
            if isinstance(detail, Exception):
                trace["details_error"] = (
                    "trace_details_unavailable"
                )
                continue

            trace["details"] = detail

        trace_result["traces"] = candidates
        traces = trace_result

    except Exception:
        logger.exception(
            "Downstream trace collection failed for service=%s",
            service,
        )
        errors.append("downstream_traces_unavailable")

    return {
        "downstream_telemetry": {
            "service": service,
            "selection": state.get(
                "downstream_selection",
                {},
            ),
            "metrics": metrics,
            "logs": logs,
            "traces": traces,
        },
        "downstream_telemetry_errors": errors,
    }

async def analyze_incident(state: dict) -> dict:
    messages = [SystemMessage(content=INCIDENT_SYSTEM_PROMPT), build_incident_message(state)]

    try:
        model = get_incident_analysis_model()
        analysis = await model.ainvoke(messages)
        return analysis.model_dump()

    except Exception:
        logger.exception("LLM incident analysis failed for service=%s", state.get("service"))
        return {
            "probable_cause": "Automated root cause analysis could not be completed.",
            "confidence": 0.0,
            "evidence": [],
            "recommended_actions": [
                "Review the collected incident evidence manually."
            ],
        }

async def retrieve_runbook_context(state: IncidentState) -> dict:
    query = build_runbook_query(state)
    
    try:
        documents = await asyncio.to_thread(retrieve_runbooks, query, k=6)
        retrieved_runbooks = []
    
        for document in documents:
            retrieved_runbooks.append({
                    "runbook_id": document.metadata.get("runbook_id"),
                    "filename": document.metadata.get("filename"),
                    "section": document.metadata.get("section"),
                    "source": document.metadata.get("source"),
                    "authoritative": document.metadata.get(
                        "authoritative",
                        False,
                    ),
                    "content": document.page_content,
                })
        return {
            "runbook_query": query,
            "retrieved_runbooks": retrieved_runbooks,
        }
    except Exception:
        logger.exception(
            "Runbook retrieval failed for service=%s",
            state.get("service"),
        )

        return {
            "runbook_query": query,
            "retrieved_runbooks": [],
        }
