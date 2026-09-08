---
title: Downstream Dependency Failure
category: dependencies
services:
  - checkout
  - payment
  - cart
  - currency
  - product-catalog
  - shipping
  - quote
technologies:
  - grpc
  - opentelemetry
  - tempo
  - loki
  - mimir
severity: high
read_only: true
---

# Downstream Dependency Failure

## Purpose
Covers incidents where an upstream service degrades because a downstream dependency fails or slows: `checkout` depends on `payment`, `cart`, `currency`, `product-catalog`, `email`, and `shipping`; `shipping` depends on `quote`; `cart` depends on the Valkey cache. Retrieve when errors or latency propagate along the call graph. A failing downstream span may be a symptom, not the origin.

## Symptoms
- Metrics: correlated error/latency rise in both caller and callee.
- Logs: caller logs "upstream error"/"connection refused"; callee logs its own failure.
- Traces: an error or slow span in the downstream service, with the caller span reflecting it.
- Kubernetes: the downstream pod may show restarts or unready endpoints.

## Signals to Check
### Metrics — error rate, latency, dependency latency
`sum by (service_name) (rate(rpc_server_duration_seconds_count{namespace="otel-demo"}[5m]))` filtered to error status; compare caller vs callee.
### Logs — connection failures, dependency errors
`{namespace="otel-demo", service_name="checkout"} |= "payment" |= "error"`.
### Traces — downstream dependencies, error spans, parent/child
`{ resource.service.name = "checkout" && status = error }` then inspect child `payment`/`cart` spans.
### Kubernetes — readiness, endpoints, restart counts
`increase(kube_pod_container_status_restarts_total{namespace="otel-demo", pod=~"payment.*"}[30m])`; endpoint readiness.

## Investigation Steps
1. Identify the degraded caller and enumerate its dependencies from the topology.
2. In Tempo, walk a failing trace parent→child to the deepest span with error/slow status; that identifies the originating dependency.
3. Confirm the downstream service independently shows the fault in its own metrics/logs.
4. Check the downstream pod's readiness, restarts, and resource state.
5. Rule out a shared dependency (flagd, PostgreSQL, Valkey) affecting multiple callers. Read-only.

## Possible Causes
- Downstream service fault — observed: the deepest error span is in `payment`; strong if `payment` metrics/logs agree.
- Downstream saturation — observed: downstream latency high, throttling/OOM present.
- Cache/DB dependency failing — observed: `cart`→Valkey or `product-catalog`→PostgreSQL span failing.
- Network between caller and callee — observed: connection refused/reset without any callee-side error.

## How to Distinguish Causes
- **Genuine downstream fault vs network.** Supported by callee-side errors matching caller-side; weakened if the callee shows no error while the caller logs connection resets (points to network — see `dns-or-network-failure.md`). Next: query callee error metrics independently.
- **Single dependency vs shared.** Supported if only one caller degrades; if many callers of the same dependency degrade together, suspect the shared dependency. Next: `{ status = error } | by(resource.service.name) | count()`.
- **Saturation vs bug.** Supported if downstream throttling/OOM is present; weakened if resources are healthy. Next: check downstream CPU/memory.

## Recommended Actions
### Immediate Investigation
Walk traces to the deepest failing span; confirm downstream-side evidence; test the shared-dependency hypothesis.
### Potential Remediation
A human operator may consider adding circuit breakers, timeouts, retries with backoff, bulkheads, or scaling/repairing the downstream if confirmed.
### Prevention
Dependency isolation; per-dependency SLOs and dashboards; retry/timeout policy; graceful degradation.

## Escalation / Unknowns
If downstream telemetry is missing, do not assume the downstream is healthy; escalate to its owning team. Missing telemetry reduces confidence.

## Correlation Guidance
Traces → Metrics: the deepest failing span names the dependency to query. Metrics → Metrics: many callers degrading together implicates a shared dependency. Logs → Traces: a caller "connection refused" line carrying a `trace_id` links to the trace.

## Evidence Safety Rules
A failing downstream span may be a symptom of an even deeper cause; keep walking the tree. Correlation of caller and callee is not proof of direction — verify callee-side. Bounded traces are samples.