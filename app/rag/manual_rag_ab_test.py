import asyncio
import json
from copy import deepcopy

from app.agent.nodes import (
    analyze_incident,
    retrieve_runbook_context,
)


BASE_STATE = {
    "alert_name": "CheckoutHighLatency",
    "cluster": "prod-app-a",
    "service": "checkout",
    "severity": "high",
    "window_start": 0,
    "window_end": 0,

    "metrics": {
        "error_rate": 0.0,
        "p95_latency_ms": 10000,
        "p99_latency_ms": 10000,
        "p95_is_bucket_ceiling": True,
        "p99_is_bucket_ceiling": True,
    },

    "traces": {
        "traces": [
            {
                "duration_ms": 22109,
                "window_relation": "within_window",
                "details": {
                    "spans": [
                        {
                            "span_id": "span-place-order",
                            "parent_span_id": None,
                            "name": "CheckoutService/PlaceOrder",
                            "service": "checkout",
                            "duration_ms": 22109,
                            "status": "OK",
                        },
                        {
                            "span_id": "span-orders-publish",
                            "parent_span_id": "span-place-order",
                            "name": "orders publish",
                            "service": "checkout",
                            "duration_ms": 22075,
                            "status": "OK",
                        },
                    ]
                },
            }
        ]
    },

    "logs": {
        "entries": [
            {
                "message": "Successful to write message. duration: 22.1s"
            }
        ]
    },

    "telemetry_errors": [],
}


async def run_without_rag():
    state = deepcopy(BASE_STATE)

    state["runbook_query"] = ""
    state["retrieved_runbooks"] = []

    return await analyze_incident(state)


async def run_with_rag():
    state = deepcopy(BASE_STATE)

    rag_result = await retrieve_runbook_context(state)
    state.update(rag_result)

    print("\nRetrieved runbooks:")
    for item in state["retrieved_runbooks"]:
        print(
            "-",
            item["runbook_id"],
            "/",
            item["section"],
        )

    return await analyze_incident(state)


async def main():
    print("\n==============================")
    print("A: WITHOUT RAG")
    print("==============================")

    without_rag = await run_without_rag()

    print(
        json.dumps(
            without_rag,
            indent=2,
            default=str,
        )
    )

    print("\n==============================")
    print("B: WITH RAG")
    print("==============================")

    with_rag = await run_with_rag()

    print(
        json.dumps(
            with_rag,
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())