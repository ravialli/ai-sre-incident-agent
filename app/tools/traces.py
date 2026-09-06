import json

from app.config.settings import settings
from app.tools.tempo import TempoClient

class TraceTool:
    def __init__(self):
        self.client = TempoClient(
            base_url= settings.tempo_base_url,
            timeout= settings.request_timeout
        )
        
    async def get_service_traces(
        self,
        service: str,
        start: int | None = None,
        end: int | None = None,
        limit: int = 20,
    ):
        traceql = f'{{ resource.service.name = {json.dumps(service)} }}'
        
        result = await self.client.search_traces(traceql=traceql, start=start, end=end, limit=limit)
        
        traces = result.get("traces") or []
        
        normalized_traces = []

        for trace in traces:
            normalized_traces.append(
                {
                    "trace_id": trace.get("traceID"),
                    "root_service": trace.get("rootServiceName"),
                    "root_trace_name": trace.get("rootTraceName"),
                    "start_time_unix_nano": trace.get("startTimeUnixNano"),
                    "duration_ms": trace.get("durationMs"),
                }
            )
        return {
            "service": service,
            "query": traceql,
            "start": start,
            "end": end,
            "traces": normalized_traces,
        }
