---
title: Service Unavailable
category: errors
services:
  - frontend
  - checkout
  - cart
  - payment
  - product-catalog
technologies:
  - kubernetes
  - grpc
  - opentelemetry
  - mimir
  - loki
  - tempo
severity: critical
read_only: true
---

# Service Unavailable

## Purpose
Covers a service being wholly or partly unreachable in the OpenTelemetry Demo: HTTP 503, gRPC UNAVAILABLE (code 14), no ready endpoints, or connection refused. Per the gRPC spec, UNAVAILABLE "indicates the service is currently unavailable. This is most likely a transient condition and may be corrected by retrying with a backoff. Note that it is not always safe to retry non-idempotent operations." Retrieve when callers report a dependency is down or a service has zero ready replicas. Unavailability can stem from the pod, the Service/endpoints, or the network.

## Symptoms
- Metrics: `kube_deployment_status_replicas_unavailable` > 0; zero ready endpoints; a spike of gRPC UNAVAILABLE / HTTP 503 at callers.
- Logs: "connection refused", "no healthy upstream" (Envoy), UNAVAILABLE.
- Traces: caller spans error immediately with no downstream child span (the call never reached the callee).
- Kubernetes: pods not `Ready`, in `CrashLoopBackOff`, or `Pending`; endpoints empty.

## Signals to Check
### Metrics — availability, error rate, RPC/HTTP status
`kube_deployment_status_replicas_unavailable{namespace="otel-demo"}`; `kube_pod_status_phase{namespace="otel-demo"}`; caller UNAVAILABLE/503 rate.
### Logs — connection refused, no healthy upstream
`{namespace="otel-demo", service_name="frontend-proxy"} |= "no healthy upstream"`.
### Traces — missing downstream child spans
`{ resource.service.name = "checkout" && status = error }` and note an absent `payment` child.
### Kubernetes — readiness, endpoints, rollout
Pod readiness; Service endpoints; `kube_deployment_status_observed_generation`.

## Investigation Steps
1. Determine scope: total outage (zero ready replicas) vs partial (some replicas unready) vs intermittent.
2. Check pod phase/readiness and endpoint population for the target service.
3. If pods are Ready but callers still get UNAVAILABLE, suspect Service/endpoints/network or a readiness-gate mismatch.
4. Inspect a caller trace: an immediate error with no callee child span means the request never landed.
5. Check for a failed rollout that left no available replicas. Read-only.

## Possible Causes
- All replicas unhealthy — observed: CrashLoop/OOM/probe failing; zero Ready.
- Failed rollout — observed: the new revision is unavailable, old replicas scaled down.
- Service/endpoint misrouting — observed: pods Ready but endpoints empty or a mismatched selector.
- Network/DNS between caller and callee — observed: connection refused with the callee healthy (see `dns-or-network-failure.md`).

## How to Distinguish Causes
- **Pod-down vs routing.** Supported for pod-down by unready/crashing pods; for routing by Ready pods with empty endpoints or caller-side connection refused while the callee is healthy. Next: compare pod readiness to Service endpoints.
- **Rollout vs organic.** Supported if unavailability starts at a rollout and old replicas are gone; weakened otherwise. Next: check rollout generation/time.
- **Network vs service.** Supported for network if the callee shows healthy metrics but callers cannot connect. Next: see `dns-or-network-failure.md`.

## Recommended Actions
### Immediate Investigation
Establish scope; check readiness and endpoints; inspect caller traces for missing child spans; verify rollout state.
### Potential Remediation
A human operator may consider rolling back, fixing probes, correcting the Service selector, or restoring network/DNS, once confirmed.
### Prevention
PodDisruptionBudgets; readiness gates and surge/maxUnavailable tuning; availability SLOs; synthetic checks on critical paths.

## Escalation / Unknowns
If callee telemetry is absent, you cannot conclude the callee is down vs merely unreachable — escalate. Absence of spans is uncertainty, not proof of total failure or of health.

## Correlation Guidance
Kubernetes → Application Telemetry: zero ready replicas explains caller UNAVAILABLE. Traces → Kubernetes: a caller error with no child span points to a delivery failure to verify against endpoints. Metrics → Metrics: `replicas_unavailable` with caller 503 corroborate.

## Evidence Safety Rules
UNAVAILABLE at a caller does not localize the fault — verify callee and network. Empty endpoints are meaningful; empty query results are not automatically zero traffic. A missing child span shows the call did not complete, not necessarily why.