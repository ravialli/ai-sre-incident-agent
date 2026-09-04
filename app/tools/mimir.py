import httpx


class MimirClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    async def query(self, promql: str) -> dict:
        url = f"{self.base_url}/api/v1/query"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                url,
                params={"query": promql},
            )

            response.raise_for_status()
            return response.json()