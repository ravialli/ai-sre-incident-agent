class MockMimirClient:

    async def query(self, promql: str) -> dict:
        if "histogram_quantile" in promql and "0.99" in promql:
            value = "3.8"

        elif "histogram_quantile" in promql and "0.95" in promql:
            value = "1.9"

        elif 'http_response_status_code=~"5.."' in promql:
            value = "8.7"

        else:
            value = "42.0"

        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {},
                        "value": [
                            0,
                            value
                        ]
                    }
                ]
            }
        }