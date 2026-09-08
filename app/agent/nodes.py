from app.tools.metrics import MetricsTool
from app.tools.logs import LogsTool
from app.tools.traces import TraceTool
import asyncio
from langchain.messages import SystemMessage
import logging

logger = logging.getLogger(__name__)

from app.agent.llm import get_incident_analysis_model
from app.agent.prompts import (
    INCIDENT_SYSTEM_PROMPT,
    build_incident_message,
)


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
    
async def collect_traces(state: dict) -> dict:
    trace_tool = TraceTool()
    try:
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
                logger.warning("Trace detail retrieval failed for trace_id=%s: %s", trace.get("trace_id"), details)
                trace["details_error"] = "trace_details_unavailable"
                continue
            
            trace["details"] = details

        return {"traces": trace_result}
    except Exception:
        logger.exception("Traces collection failed for service = %s", state.get("service"))
        return {"traces": {}, "telemetry_errors": ["traces_unavailable"]}

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