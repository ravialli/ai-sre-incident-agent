from app.config.settings import settings
from app.tools.mimir import MimirClient


class MetricsTool:
    def __init__(self):
        self.client = MimirClient(
    settings.mimir_base_url,
    settings.request_timeout,
)
        
    def _extract_value(self, response: dict) -> float:
        result = response["data"]["result"]

        if not result:
            return 0.0

        return float(result[0]["value"][1])

    async def get_service_metrics(self, service: str) -> dict:
        job = f"opentelemetry-demo/{service}"

        queries = {
            "request_rate": f'''
sum(
  rate(
    http_server_request_duration_count{{
      job="{job}"
    }}[5m]
  )
)
''',

            "error_rate": f'''
(
  100 *
  sum(
    rate(
      http_server_request_duration_count{{
        job="{job}",
        http_response_status_code=~"5.."
      }}[5m]
    )
  )
  /
  sum(
    rate(
      http_server_request_duration_count{{
        job="{job}"
      }}[5m]
    )
  )
)
or vector(0)
''',

            "p95_latency": f'''
histogram_quantile(
  0.95,
  sum by (le) (
    rate(
      http_server_request_duration_bucket{{
        job="{job}"
      }}[5m]
    )
  )
)
''',

            "p99_latency": f'''
histogram_quantile(
  0.99,
  sum by (le) (
    rate(
      http_server_request_duration_bucket{{
        job="{job}"
      }}[5m]
    )
  )
)
'''
        }

        results = {}

        for name, query in queries.items():
            results[name] = await self.client.query(query)

        return {
            "service": service,
            "request_rate": self._extract_value(results["request_rate"]),
            "error_rate": self._extract_value(results["error_rate"]),
            "p95_latency": self._extract_value(results["p95_latency"]),
            "p99_latency": self._extract_value(results["p99_latency"]),
        }