from app.tools.metrics import MetricsTool
from app.tools.logs import LogsTool
from app.tools.traces import TraceTool


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
    
    traces = await trace_tool.get_service_traces(state["service"], start=state["window_start"],end=state["window_end"])
    
    return {"traces": traces}