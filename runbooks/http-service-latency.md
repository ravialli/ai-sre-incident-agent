---
title: HTTP Service Latency
category: latency
services:
  - frontend
  - frontend-proxy
  - shipping
  - email
  - quote
technologies:
  - opentelemetry
  - envoy
  - tempo
  - mimir
  - loki
severity: medium-high
read_only: true
---

# HTTP Service Latency

## Purpose
Covers elevated latency on HTTP paths in the OpenTelemetry Demo: `frontend-proxy` (Envoy)→`frontend`, `frontend`→`shipping`, `checkout`→`email`, `shipping`→`quote`. Retrieve when HTTP server request-duration percentiles rise for these services. HTTP latency is not automatically a downstream fault.

## Symptoms
- Metrics: rising p95/p99 of `http_server_request_duration_seconds_bucket`.
- Logs: slow-request lines; upstream timeout messages at Envoy.
- Traces: HTTP server spans dominating the critical path; long child spans to downstream services.
- Kubernetes: possible CPU throttling; otherwise normal.

## Signals to Check
### Metrics — latency percentiles, request rate, HTTP status, saturation
`histogram_quantile(0.95, sum by (le) (rate(http_server_request_duration_seconds_bucket{namespace="otel-demo", service_name="shipping"}[5m])))`; request rate by route.
### Logs — timeout messages, dependency errors
`{namespace="otel-demo", service_name="shipping"} |= "timeout"`.
### Traces — slow spans, critical-path latency, downstream dependencies
`{ resource.service.name = "shipping" && duration > 1s } | select(span.http.route, span.http.status_code)`. 
### Kubernetes — resource requests/limits, node pressure
`kube_pod_container_resource_limits{namespace="otel-demo", pod=~"shipping.*"}`.

## Investigation Steps
1. Identify the slow route/endpoint via `http_server_request_duration_seconds_bucket` broken down by `http_route`.
2. Distinguish Envoy (`frontend-proxy`) added latency from `frontend` service latency by comparing the two spans in the same trace.
3. Pull slow traces; determine whether `shipping`'s own handler time or its child call to `quote` dominates.
4. Check CPU throttling and any request-rate increase on the slow pod.
5. Compare against a healthy window. Read-only throughout.

## Possible Causes
- Downstream HTTP dependency slow — observed: the child span to `quote` dominates; inference; hypothesis until `quote` metrics confirm.
- Proxy-added latency — observed: a gap between `frontend-proxy` and `frontend` spans.
- CPU saturation/throttling — observed: throttling counter rising; supportive only.
- Load-driven queueing — observed: request rate up.

## How to Distinguish Causes
- **Downstream vs local.** Supported if the `quote` child span dominates the `shipping` parent; weakened if parent self-time dominates. Next: query `quote` p95.
- **Proxy vs app.** Supported if the `frontend-proxy` span far exceeds the `frontend` span; weakened if they are equal. Next: compare span durations in one trace.
- **CPU saturation.** Supported when throttling and latency rise together; weakened if throttling is flat. Latency alone never proves CPU saturation.

## Recommended Actions
### Immediate Investigation
Break latency by route; compare proxy vs app spans; find the dominating child; check throttling and load.
### Potential Remediation
A human operator may consider scaling replicas, tuning timeouts, adding caching, or optimizing the downstream service if evidence confirms.
### Prevention
Route-level latency SLOs; Envoy-vs-app latency dashboards; capacity planning; timeout tuning.

## Escalation / Unknowns
If slow traces are sampled out, confidence drops. Escalate when the user-facing `frontend` path breaches SLO. Missing telemetry is uncertainty, not health.

## Correlation Guidance
Metrics → Traces: a p95 spike guides trace search. Traces → Traces: compare multiple slow traces before concluding. Kubernetes → Application Telemetry: throttling correlation is not proof.

## Evidence Safety Rules
Bucket ceilings approximate latency; a trace overlapping the window may have started before it. The slowest span is not automatically the root cause. Bounded results are samples.