from app.tools.metrics import MetricsTool
from app.tools.logs import LogsTool


async def collect_metrics(state: dict) -> dict:
    metrics_tool = MetricsTool()

    metrics = await metrics_tool.get_service_metrics(
        state["service"]
    )

    return {
        "metrics": metrics
    }

async def collect_logs(state: dict) -> dict:
    logs_tool = LogsTool()

    logs = await logs_tool.get_service_logs(
        state["service"]
    )

    return {
        "logs": logs
    }