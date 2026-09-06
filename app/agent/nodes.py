from app.tools.metrics import MetricsTool
from app.tools.logs import LogsTool
from app.tools.traces import TraceTool
import asyncio

async def collect_metrics(state: dict) -> dict:
    metrics_tool = MetricsTool()

    metrics = await metrics_tool.get_service_metrics(state["service"], time=state["window_end"])

    return {
        "metrics": metrics
    }

async def collect_logs(state: dict) -> dict:
    logs_tool = LogsTool()

    logs = await logs_tool.get_service_logs(state["service"], start=state["window_start"], end=state["window_end"])

    return {
        "logs": logs
    }
    
async def collect_traces(state: dict) -> dict:
    trace_tool = TraceTool()
    
    trace_result = await trace_tool.get_service_traces(state["service"], start=state["window_start"], end=state["window_end"])
    
    trace_summaries = trace_result.get("traces") or []
    
    candidates_with_ids = []

    for trace in trace_summaries:
        if trace.get("trace_id"):
            candidates_with_ids.append(trace)

        if len(candidates_with_ids) == 3:
            break
    
    tasks = [trace_tool.get_trace_details(trace_id=trace["trace_id"]) for trace in candidates_with_ids]
    
    trace_details = await asyncio.gather(*tasks, return_exceptions=True)
    for trace, details in zip(candidates_with_ids, trace_details):
        if isinstance(details, Exception):
            trace["details_error"] = str(details)
            continue
        
        trace["details"] = details

    return {"traces": trace_result}

async def analyze_incident(state: dict) -> dict:
    metrics = state.get("metrics") or {}
    logs = state.get("logs") or {}
    traces = state.get("traces") or {}
    
    error_rate = metrics.get("error_rate", 0.0)
    p95_latency = metrics.get("p95_latency", 0.0)
    p99_latency = metrics.get("p99_latency", 0.0)

    trace_summaries = traces.get("traces") or []

    error_spans = []

    for trace in trace_summaries:
        details = trace.get("details") or {}

        for span in details.get("spans") or []:
            if span.get("status") == "STATUS_CODE_ERROR":
                error_spans.append(span)
                
    evidence = []
    probable_cause = ""
    confidence = 0.3 if error_spans else 0.1
    
    if error_spans:
        probable_cause = ("Trace-level failures were observed, but the root cause has not yet been determined.")
    else:
        probable_cause = ("No clear root cause was identified from the collected trace evidence.")
    
    if error_spans:
        evidence.append(
            f"Found {len(error_spans)} trace spans with error status."
        )
        
    recommended_actions = ["Review the error spans and correlated logs for the incident window."]

    return {
        "probable_cause": probable_cause,
        "confidence": confidence,
        "evidence": evidence,
        "recommended_actions": recommended_actions
    }