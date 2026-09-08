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
            trace_start_ns = trace.get("startTimeUnixNano")
            duration_ms = trace.get("durationMs")

            trace_start_unix = None
            trace_end_unix = None
            window_relation = "unknown"
            
            if trace_start_ns is not None and duration_ms is not None:
                trace_start_unix = int(trace_start_ns) / 1_000_000_000
                trace_end_unix = trace_start_unix + (float(duration_ms) / 1000)
                
                if start is not None and end is not None:
                    if trace_end_unix < start:
                        window_relation = "before_window"

                    elif trace_start_unix > end:
                        window_relation = "after_window"

                    elif trace_start_unix <= start and trace_end_unix >= end:
                        window_relation = "spans_entire_window"

                    elif trace_start_unix < start:
                        window_relation = "overlaps_window_start"

                    elif trace_end_unix > end:
                        window_relation = "overlaps_window_end"

                    else:
                        window_relation = "within_window"
                        
            normalized_traces.append(
                {
                    "trace_id": trace.get("traceID"),
                    "root_service": trace.get("rootServiceName"),
                    "root_trace_name": trace.get("rootTraceName"),
                    "start_time_unix_nano": trace_start_ns,
                    "duration_ms": duration_ms,
                    "trace_start_unix": trace_start_unix,
                    "trace_end_unix": trace_end_unix,
                    "window_relation": window_relation,
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
