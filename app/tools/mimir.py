import httpx


class MimirClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def query(self, promql: str) -> dict:
        url = f"{self.base_url}/api/v1/query"

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.get(
                url,
                params={"query": promql},
            )

            response.raise_for_status()

            payload = response.json()

        if payload.get("status") != "success":
            raise RuntimeError(
                f"Mimir query failed: {payload}"
            )

        return payload