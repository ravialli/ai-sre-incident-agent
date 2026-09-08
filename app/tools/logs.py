from app.config.settings import settings
from app.tools.loki import LokiClient
import json


class LogsTool:
    def __init__(self):
        self.client = LokiClient(base_url=settings.loki_base_url, tenant_id=settings.loki_tenant_id, timeout=settings.request_timeout)

    async def get_service_logs(self, service: str, start: int, end: int, limit: int = 100) -> dict:

        query = (f'{{service_name={json.dumps(service)}}}')

        payload =  await self.client.query_range(logql=query, start=start, end=end, limit=limit)
        
        streams = payload.get("data", {}).get("result") or []
        
        entries = []
        
        for stream in streams:
            labels = stream.get("stream") or {}
            values = stream.get("values") or []
            
            for value in values:
                if len(value) < 2:
                    continue

                entries.append(
                    {
                        "timestamp": value[0],
                        "message": value[1],
                        "labels": labels,
                    }
                )
        return {
            "service": service,
            "query": query,
            "start": start,
            "end": end,
            "limit": limit,
            "entries_returned": len(entries),
            "entries": entries,
        }