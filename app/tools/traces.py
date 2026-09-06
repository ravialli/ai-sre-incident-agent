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
            
    async def get_trace_details(self, trace_id: str) -> dict:

        result = await self.client.get_trace(trace_id=trace_id)

        trace = result.get("trace") or {}
        resource_spans = trace.get("resourceSpans") or []

        normalized_spans = []

        for resource_span in resource_spans:
            
            resource = resource_span.get("resource") or {}
            resource_attributes = resource.get("attributes") or []
            service_name = None
            
            for attribute in resource_attributes:
                if attribute.get("key") == "service.name":
                    service_name = (attribute.get("value", {}).get("stringValue"))
                    break

            scope_spans = resource_span.get("scopeSpans") or []

            for scope_span in scope_spans:

                spans = scope_span.get("spans") or []

                for span in spans:
                    status = span.get("status") or {}
                    duration_ms = None
                    start = span.get("startTimeUnixNano")
                    end = span.get("endTimeUnixNano")
        
                    if start is not None and end is not None:
                        duration_ms = (int(end) - int(start)) / 1_000_000
                    normalized_spans.append(
                        {
                            "service": service_name,
                            "span_id": span.get("spanId"),
                            "parent_span_id": span.get("parentSpanId"),
                            "name": span.get("name"),
                            "start_time_unix_nano": start,
                            "end_time_unix_nano": end,
                            "duration_ms": duration_ms,
                            "status": status.get("code", "STATUS_CODE_UNSET"),
                            "status_message": status.get("message"),
                        }
                    )

        return {"trace_id": trace_id, "spans": normalized_spans}
