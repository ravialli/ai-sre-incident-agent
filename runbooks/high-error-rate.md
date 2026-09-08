---
title: High Error Rate
category: errors
services:
  - frontend
  - checkout
  - cart
  - payment
  - product-catalog
technologies:
  - opentelemetry
  - mimir
  - loki
  - tempo
  - kubernetes
severity: high
read_only: true
---

# High Error Rate

## Purpose
Covers a sustained rise in failed requests (HTTP 5xx, gRPC non-OK) across one or more OpenTelemetry Demo services. Retrieve this runbook when the error ratio for a service such as `frontend`, `checkout`, `payment`, or `product-catalog` exceeds its baseline. Error rate alone does not identify a root cause; the goal here is disciplined evidence gathering from metrics, logs, and traces.

## Symptoms
- Metrics: rising ratio of `http_server_request_duration_seconds_count{http_response_status_code=~"5.."}` to total request count; increase in `rpc_server_duration_seconds_count` with an error status.
- Logs: application error lines, stack traces, `level=error`.
- Traces: spans with `status = error`; `span.http.status_code >= 500`; gRPC error codes such as UNAVAILABLE (14) or INTERNAL (13).
- Kubernetes: possibly normal pod status, or restarts if errors coincide with crashes.

## Signals to Check
### Metrics — request rate, error rate, latency percentiles, RPC status, HTTP status
`sum by (http_response_status_code) (rate(http_server_request_duration_seconds_count{namespace="otel-demo", service_name="frontend"}[5m]))`.
Error ratio: `sum(rate(http_server_request_duration_seconds_count{service_name="checkout", http_response_status_code=~"5.."}[5m])) / sum(rate(http_server_request_duration_seconds_count{service_name="checkout"}[5m]))`.
### Logs — error messages, dependency errors, structured log labels
`{namespace="otel-demo", service_name="checkout"} | json | level="error"`.
### Traces — error spans, parent/child relationships, downstream dependencies
`{ resource.service.name = "checkout" && status = error } | select(span.http.status_code, span.rpc.grpc.status_code)`. 
### Kubernetes — pod phase, container restart count, rollout status
`increase(kube_pod_container_status_restarts_total{namespace="otel-demo"}[30m])`; check recent deployment rollout timing.

## Investigation Steps
1. Confirm the error ratio and window in Mimir; compare against the prior 24h same-time window.
2. Determine whether errors concentrate in one service or span the call graph (`frontend`→`checkout`→`payment`).
3. Query Tempo for error traces in the window; find which span first turns `status = error`.
4. Correlate one failing `trace_id` to Loki logs for that service.
5. Check for a recent rollout or an enabled fault flag (`paymentServiceFailure`, `cartServiceFailure`, `productCatalogFailure`).
6. Inspect Kubernetes events and restarts for the implicated service. All actions are read-only; any change is a recommendation for a human operator.

## Possible Causes
- Downstream dependency failing — observed evidence: error spans originate in `payment`; inference: upstream 5xx is propagation; treat as hypothesis until the downstream confirms it independently.
- Bad deployment/regression — observed: error onset aligns with a rollout; inference: causal; hypothesis until the diff is reviewed.
- Feature-flag fault injection — observed: a fault flag is enabled in flagd; strong signal.
- Resource exhaustion producing errors — observed: restarts/OOM present (see `kubernetes-oomkill.md`).

## How to Distinguish Causes
- **Downstream dependency vs local bug.** Supporting evidence: the deepest span holding the first error status. If `payment` spans error first and `checkout` merely relays them, the origin is downstream. Weakened if `checkout` errors precede any downstream call. Competing explanation: a shared dependency (flagd, PostgreSQL). Next read-only query: `{ status = error } | by(resource.service.name) | count()`  to rank originating services.
- **Deployment regression.** Supported if the error onset is a step change at a rollout; weakened if errors predate the rollout. Next: compare `kube_deployment_status_observed_generation` change time to error onset.
- **Feature flag.** Supported by flagd logs/config showing the flag on. Next: read flagd configuration (read-only).

## Recommended Actions
### Immediate Investigation
Rank originating services in Tempo; pull representative failing traces; correlate to logs by `trace_id`; confirm rollout timing.
### Potential Remediation
A human operator may consider rolling back a recent deployment, disabling a fault-injection flag, or failing over a dependency if evidence confirms the cause.
### Prevention
Per-service SLO error-budget alerts; canary deploys; dashboards for error ratio by `service_name` and `http_response_status_code`; structured error logging that always carries `trace_id`.

## Escalation / Unknowns
If error traces are sampled out or logs are truncated, confidence drops; missing telemetry is not evidence of health. Escalate to the owning team when the originating service is external to the demo or when the error ratio threatens a critical SLO.

## Correlation Guidance
Metrics → Traces: an error-ratio spike guides the Tempo query to the same window. Traces → Logs: a failing `trace_id` correlates to Loki error lines. Kubernetes → Application Telemetry: restarts may coincide with errors but do not by themselves establish causation.

## Evidence Safety Rules
Correlation is not proof of causation; a failing downstream span may be a symptom, not the origin. Empty error-log results are not proof of zero errors when retention or sampling is limited. Bounded log queries are samples. Tie every recommendation to observed evidence or label it a hypothesis; prefer queries that separate downstream-origin from local-origin.