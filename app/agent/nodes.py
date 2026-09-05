from app.tools.metrics import MetricsTool
from app.tools.mock_mimir import MockMimirClient


async def collect_metrics(state: dict) -> dict:
    metrics_tool = MetricsTool(
        client = MockMimirClient()
    )

    metrics = await metrics_tool.get_service_metrics(
        state["service"]
    )

    return {
        "metrics": metrics
    }