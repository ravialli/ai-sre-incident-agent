from app.config.settings import settings
from app.tools.mimir import MimirClient
import json

LATENCY_BUCKET_CEILING_SECONDS = 10.0

class MetricsTool:
    def __init__(self):
        self.client = MimirClient(settings.mimir_base_url, settings.request_timeout)
        
    def _extract_value(self, response: dict) -> float | None:
        result = response["data"]["result"]

        if not result:
            return None

        return float(result[0]["value"][1])
      
    async def _detect_server_protocol(self, job: str, time: int | None = None) -> str:
      http_query = f'count(http_server_request_duration_count{{job={json.dumps(job)}}})'
      rpc_query = f'count(rpc_server_call_duration_count{{job={json.dumps(job)}}})'
      http_response = await self.client.query(http_query,time=time)
      rpc_response = await self.client.query(rpc_query, time=time)
      
      http_count = self._extract_value(http_response)
      rpc_count = self._extract_value(rpc_response)
      
      http_exists = http_count is not None and http_count > 0
      rpc_exists = rpc_count is not None and rpc_count > 0
      
      if http_exists and rpc_exists:
        raise RuntimeError(
            f"Both HTTP and RPC server metrics were found for job={job}"
        )

      if http_exists:
          return "http"

      if rpc_exists:
          return "rpc"

      raise RuntimeError(
          f"No HTTP or RPC server metrics were found for job={job}"
      )


    async def get_service_metrics(self, service: str, time: int | None = None) -> dict:
        job = f"opentelemetry-demo/{service}"
        
        protocol = await self._detect_server_protocol(job, time=time)
        
        if protocol == "http":
          count_metric = "http_server_request_duration_count"
          bucket_metric = "http_server_request_duration_bucket"
          error_filter = 'http_response_status_code=~"5.."'

        elif protocol == "rpc":
          count_metric = "rpc_server_call_duration_count"
          bucket_metric = "rpc_server_call_duration_bucket"
          error_filter = 'rpc_response_status_code!="OK"'

        queries = {
            "request_rate": f'sum(rate({count_metric}{{job={json.dumps(job)}}}[5m]))',
              
            "error_rate": f'(100 * sum(rate({count_metric}{{job={json.dumps(job)}, {error_filter}}}[5m])) / sum(rate({count_metric}{{job={json.dumps(job)}}}[5m]))) or vector(0)',
              
            "p95_latency": f'histogram_quantile(0.95, sum by (le) (rate({bucket_metric}{{job={json.dumps(job)}}}[5m])))',

            "p99_latency": f'histogram_quantile(0.99, sum by (le) (rate({bucket_metric}{{job={json.dumps(job)}}}[5m])))'
          }
        
        results = {}

        for name, query in queries.items():
            results[name] = await self.client.query(query, time=time)
        
        p95 = self._extract_value(results["p95_latency"])
        p99 = self._extract_value(results["p99_latency"])
        
        p95_is_bucket_ceiling = (p95 is not None and p95 >= LATENCY_BUCKET_CEILING_SECONDS)

        p99_is_bucket_ceiling = (p99 is not None and p99 >= LATENCY_BUCKET_CEILING_SECONDS)

        return {
            "service": service,
            "protocol": protocol,
            "request_rate": self._extract_value(results["request_rate"]),
            "error_rate": self._extract_value(results["error_rate"]),
            "p95_latency_ms": p95 * 1000 if p95 is not None else None,
            "p99_latency_ms": p99 * 1000 if p99 is not None else None,
            "p95_is_bucket_ceiling": p95_is_bucket_ceiling,
            "p99_is_bucket_ceiling": p99_is_bucket_ceiling,   
        }
