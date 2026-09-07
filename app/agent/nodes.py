from app.tools.metrics import MetricsTool
from app.tools.logs import LogsTool
from app.tools.traces import TraceTool
import asyncio
from langchain.messages import SystemMessage

from app.agent.llm import get_incident_analysis_model
from app.agent.prompts import (
    INCIDENT_SYSTEM_PROMPT,
    build_incident_message,
)


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
    model = get_incident_analysis_model()

    messages = [
        SystemMessage(content=INCIDENT_SYSTEM_PROMPT),
        build_incident_message(state),
    ]

    try:
        analysis = await model.ainvoke(messages)
        return analysis.model_dump()

    except Exception:
        return {
            "probable_cause": "Automated root cause analysis could not be completed.",
            "confidence": 0.0,
            "evidence": [
                "Metrics, logs, and traces were collected, but LLM analysis was unavailable."
            ],
            "recommended_actions": [
                "Review the collected incident evidence manually."
            ],
        }