import httpx


class LokiClient:
    def __init__(self, base_url: str, tenant_id: str, timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.tenant_id = tenant_id
        self.timeout = timeout

    async def query_range(self, logql: str, start: int, end: int, limit: int = 100) -> dict:
        
        start_ns = start * 1_000_000_000
        end_ns = end * 1_000_000_000

        url = f"{self.base_url}/loki/api/v1/query_range"

        headers = {"X-Scope-OrgID": self.tenant_id}

        params = {"query": logql, "start": start_ns, "end": end_ns, "limit": limit, "direction": "backward"}

        async with httpx.AsyncClient(timeout=self.timeout) as client:

            response = await client.get(url, headers=headers, params=params)

            response.raise_for_status()

            payload = response.json()

        if payload.get("status") != "success":
            raise RuntimeError(f"Loki query failed: {payload}")

        return payload