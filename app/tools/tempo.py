import httpx


class TempoClient:
    def __init__(
        self,
        base_url: str,
        timeout: float = 10.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    async def search_traces(
        self,
        traceql: str,
        start: int | None = None,
        end: int | None = None,
        limit: int = 20,
    ) -> dict:

        url = f"{self.base_url}/api/search"

        params = {
            "q": traceql,
            "limit": limit,
        }

        if start is not None:
            params["start"] = start

        if end is not None:
            params["end"] = end

        async with httpx.AsyncClient(
            timeout=self.timeout
        ) as client:
            response = await client.get(
                url,
                params=params,
            )

            response.raise_for_status()
            return response.json()
        
    async def get_trace(
        self,
        trace_id: str,
        start: int | None = None,
        end: int | None = None,
    ) -> dict:
        url = f"{self.base_url}/api/v2/traces/{trace_id}"
        
        params = {}
        if start is not None:
            params["start"] = start
        
        if end is not None:
            params["end"] = end
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                url,
                params=params,
            )
            
            response.raise_for_status()
            return response.json()