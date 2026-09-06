import time

import httpx


class LokiClient:
    def __init__(
        self,
        base_url: str,
        tenant_id: str,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.tenant_id = tenant_id
        self.timeout = timeout

    async def query_range(
        self,
        logql: str,
        minutes: int = 15,
        limit: int = 100,
    ) -> dict:

        end = time.time_ns()
        start = end - minutes * 60 * 1_000_000_000

        url = f"{self.base_url}/loki/api/v1/query_range"

        headers = {
            "X-Scope-OrgID": self.tenant_id
        }

        params = {
            "query": logql,
            "start": start,
            "end": end,
            "limit": limit,
            "direction": "backward",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:

            response = await client.get(
                url,
                headers=headers,
                params=params,
            )

            response.raise_for_status()

            payload = response.json()

        if payload.get("status") != "success":
            raise RuntimeError(
                f"Loki query failed: {payload}"
            )

        return payload