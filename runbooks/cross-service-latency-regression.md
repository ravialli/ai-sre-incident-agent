---
title: Cross-Service Latency Regression
category: latency
services:
  - frontend
  - checkout
  - product-catalog
  - cart
  - payment
  - currency
technologies:
  - opentelemetry
  - tempo
  - mimir
  - loki
  - kubernetes
severity: high
read_only: true
---

# Cross-Service Latency Regression

## Purpose
Covers a latency regression that spans multiple services along a request path in the OpenTelemetry Demo — e.g. the `frontend`→`checkout`→(`cart`, `currency`, `payment`, `product-catalog`) flow gets slower after a change. Retrieve when end-to-end latency rises but no single service is obviously at fault. The goal is to localize the added latency to a specific hop before generalizing.

## Symptoms
- Metrics: end-to-end p95 up at `frontend`/`frontend-proxy`; several services' durations up modestly.
- Logs: no single dominant error; possibly increased retries.
- Traces: total trace duration up; the added time may sit in one hop or be spread thin.
- Kubernetes: a recent rollout across one or more services; possible resource shifts.

## Signals to Check
### Metrics — latency percentiles across services, request rate
Compare p95 of `http_server_request_duration_seconds_bucket` and `rpc_server_duration_seconds_bucket` per service before vs after the regression start.
### Logs — retries, timeouts, deploy markers
`{namespace="otel-demo"} |~ "retry|deadline"`.
### Traces — critical path, per-hop breakdown
Use Tempo to compare the span breakdown of slow current traces vs a healthy baseline; identify which hop's self-time grew.
### Kubernetes — rollout timing, resource changes
`kube_deployment_status_observed_generation`; resource limits before vs after.

## Investigation Steps
1. Pin the regression start time from end-to-end p95 and align it to any deployments across services.
2. Decompose a representative slow trace hop-by-hop; compute each span's self-time (duration minus children) and compare to baseline.
3. Determine whether one hop grew (localized) or every hop grew slightly (systemic: node pressure, DNS, collector overhead, or a shared dependency).
4. Check the suspected hop for CPU throttling, DB slowness, or downstream dependency issues using the relevant runbook.
5. Confirm the finding across multiple traces before generalizing. Read-only.

## Possible Causes
- Regression in one service after deploy — observed: one hop's self-time steps up at its rollout.
- Shared-dependency slowdown — observed: multiple hops touching PostgreSQL/flagd/Valkey grew together.
- Infrastructure-wide factor — observed: node pressure or DNS latency affecting all hops.
- Increased load raising queueing across the path — observed: request rate up.

## How to Distinguish Causes
- **Localized vs systemic.** Supported for localized when one hop's self-time grew and others are flat; for systemic when many hops grew proportionally. Next: per-span self-time comparison across several traces.
- **Deploy-driven vs load-driven.** Supported for deploy when the step aligns with a rollout at flat load; for load when latency tracks request rate. Next: overlay p95 with rollout time and request rate.
- **Shared dependency vs independent.** Supported when the common factor across slow hops is one dependency (e.g. all query PostgreSQL). Next: query that dependency's latency (`database-latency.md`).

## Recommended Actions
### Immediate Investigation
Fix the regression start time; decompose slow traces by self-time; classify localized vs systemic; verify across multiple traces.
### Potential Remediation
A human operator may consider rolling back the implicated deploy, addressing the shared dependency, or relieving infrastructure pressure, once confirmed.
### Prevention
Per-hop and end-to-end latency SLOs; deploy markers on dashboards; canary/latency-regression gates in CI; baseline trace comparisons.

## Escalation / Unknowns
If baseline traces are unavailable or sampling hides the slow path, localization is limited — escalate with the per-hop evidence gathered. Missing baseline data reduces confidence; it does not imply the path is unchanged.

## Correlation Guidance
Metrics → Traces: an end-to-end p95 rise guides selection of slow traces to decompose. Traces → Metrics: the hop whose self-time grew names the service metric to drill into. Kubernetes → Metrics: rollout timing aligned to the regression start supports (but does not prove) a deploy cause.

## Evidence Safety Rules
The slowest span is not automatically the root cause — use self-time and compare multiple traces. A trace overlapping the window may predate it. Correlation of a rollout with the regression is not proof; verify with a per-hop diff. Histogram bucket ceilings approximate latency.