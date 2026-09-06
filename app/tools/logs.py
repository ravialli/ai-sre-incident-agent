from app.config.settings import settings
from app.tools.loki import LokiClient


class LogsTool:
    def __init__(self):
        self.client = LokiClient(
            base_url=settings.loki_base_url,
            tenant_id=settings.loki_tenant_id,
            timeout=settings.request_timeout,
        )

    async def get_service_logs(
        self,
        service: str,
        minutes: int = 15,
    ) -> dict:

        query = (
            f'{{service_name="{service}"}}'
        )

        return await self.client.query_range(
            logql=query,
            minutes=minutes,
        )