---
title: gRPC Service Latency
category: latency
services:
  - checkout
  - cart
  - product-catalog
  - currency
  - recommendation
  - ad
technologies:
  - grpc
  - opentelemetry
  - tempo
  - mimir
  - loki
severity: medium-high
read_only: true
---

# gRPC Service Latency

## Purpose
Covers elevated latency on gRPC call paths in the OpenTelemetry Demo, e.g. `frontend`→`product-catalog`, `checkout`→`cart`, `checkout`→`currency`, `recommendation`→`product-catalog`. Retrieve when gRPC server or client duration percentiles rise. gRPC latency is not automatically a network problem or a CPU problem.

## Symptoms
- Metrics: rising p95/p99 of `rpc_server_duration_seconds_bucket` or `rpc_client_duration_seconds_bucket` for a gRPC service.
- Logs: slow-handler warnings; deadline messages.
- Traces: gRPC spans (`span.rpc.system = "grpc"`) dominating the critical path; `span.rpc.grpc.status_code = 4` (DEADLINE_EXCEEDED) on timeouts.
- Kubernetes: possible CPU throttling on the slow pod, or none.

## Signals to Check
### Metrics — latency percentiles, RPC status, saturation
`histogram_quantile(0.95, sum by (le) (rate(rpc_server_duration_seconds_bucket{namespace="otel-demo", service_name="product-catalog"}[5m])))`.
Throttling: `rate(container_cpu_cfs_throttled_seconds_total{namespace="otel-demo", pod=~"product-catalog.*"}[5m])`.
### Logs — timeout messages, dependency errors
`{namespace="otel-demo", service_name="product-catalog"} |= "deadline"`.
### Traces — slow spans, parent/child, critical-path latency
`{ resource.service.name = "product-catalog" && kind = server && duration > 500ms }`.
### Kubernetes — resource requests/limits, node pressure
`kube_pod_container_resource_limits{namespace="otel-demo", resource="cpu", pod=~"product-catalog.*"}`.

## Investigation Steps
1. Identify the slow gRPC service and method via `rpc_server_duration_seconds_bucket` broken down by `rpc_method`.
2. Determine whether server-side duration is high or only client-side; client-high but server-low points to network/connection or caller-side queueing.
3. Pull slow Tempo traces and find the dominating span; use parent/child to see whether it is `product-catalog` server work or a downstream child (`product-catalog`→PostgreSQL).
4. Check for CPU throttling and memory pressure on the slow pod.
5. Compare against a healthy earlier window. Read-only throughout.

## Possible Causes
- Downstream DB slowness — observed: the `product-catalog` slow span is its `db_client_operation_duration_seconds` child; inference: DB-bound; hypothesis until DB metrics confirm.
- CPU saturation/throttling — observed: `container_cpu_cfs_throttled_seconds_total` rising; supportive, not proof (latency alone never proves CPU saturation).
- Connection/channel issues — observed: client duration high, server low; DEADLINE_EXCEEDED spans.
- Increased load — observed: request rate up alongside latency.

## How to Distinguish Causes
- **DB-bound vs compute-bound.** Supported if the child DB span dominates the parent gRPC span; weakened if server CPU time dominates with no large child span. Next: `histogram_quantile(0.95, sum by (le) (rate(db_client_operation_duration_seconds_bucket{service_name="product-catalog"}[5m])))`.
- **CPU saturation.** Supported when throttling and latency rise together; weakened if throttling is flat. Competing: GC pauses. Next: inspect throttled periods vs CPU usage against the limit.
- **Network/channel.** Supported when client >> server duration and DEADLINE_EXCEEDED appears; weakened if server duration itself is high. Next: compare client vs server histograms for the same method.

## Recommended Actions
### Immediate Investigation
Break latency down by method; separate server vs client duration; find the dominating span; check throttling and DB child spans.
### Potential Remediation
A human operator may consider raising CPU limits, tuning DB queries/indexes, adjusting gRPC deadlines/retries, or scaling replicas if evidence confirms the cause.
### Prevention
Latency SLOs per gRPC method; dashboards separating client/server duration; capacity planning; deadline and retry budgets.

## Escalation / Unknowns
If sampling drops the slow traces, confidence is reduced. Escalate when a critical path (`checkout`→`payment`/`cart`) breaches SLO. Missing spans do not prove the path is healthy.

## Correlation Guidance
Metrics → Traces: a p95 spike guides trace search to the window. Traces → Metrics: the dominating child span points to which downstream metric to query. Kubernetes → Application Telemetry: throttling may explain latency but correlation is not proof.

## Evidence Safety Rules
Histogram bucket ceilings are approximate, not exact latencies. The slowest span is not automatically the root cause. Correlation between throttling and latency is not causation. Bounded trace results are samples; compare multiple traces before generalizing.