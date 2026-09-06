from app.config.settings import settings
from app.tools.loki import LokiClient
import json


class LogsTool:
    def __init__(self):
        self.client = LokiClient(base_url=settings.loki_base_url, tenant_id=settings.loki_tenant_id, timeout=settings.request_timeout)

    async def get_service_logs(self, service: str, start: int, end: int, limit: int = 100) -> dict:

        query = (f'{{service_name={json.dumps(service)}}}')

        return await self.client.query_range(
            logql=query,
            start=start,
            end=end,
            limit=limit,
        )