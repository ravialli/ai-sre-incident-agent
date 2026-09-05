import asyncio

from app.tools.metrics import MetricsTool
from app.tools.mock_mimir import MockMimirClient


async def main():
    metrics = MetricsTool(
        client=MockMimirClient()
    )

    result = await metrics.get_service_metrics("checkout")

    print(result)


asyncio.run(main())