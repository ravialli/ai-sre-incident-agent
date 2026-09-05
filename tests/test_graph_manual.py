import asyncio

from app.agent.graph import incident_graph


async def main():
    result = await incident_graph.ainvoke({
        "alert_name": "HTTP p95 Latency High",
        "cluster": "prod-app-a",
        "service": "checkout",
        "severity": "warning",
    })

    print(result)


asyncio.run(main())