---
title: Telemetry Export Failure
category: observability
services:
  - all
technologies:
  - opentelemetry
  - alloy
  - mimir
  - loki
  - tempo
  - kubernetes
severity: medium-high
read_only: true
related:
  - partial-telemetry-loss.md
  - trace-incompleteness.md
  - service-unavailable.md
---

# Telemetry Export Failure

> **Demo runbook** for the `ai-sre-incident-agent` project. Not production-authoritative.
> All steps are **read-only**. Pipeline changes are recommendations for a human operator only.

## Purpose

Covers incidents where metrics, logs, or traces **stop arriving entirely** in Mimir, Loki, or Tempo — for
example OTLP export failures to Alloy or a collector. The critical task is to separate an **application
failure** from an **observability pipeline failure**, because the two look identical on a dashboard: flat
lines and missing data.

Scope note for retrieval: this runbook covers a hard gap where a signal stops. For a *reduced but
non-zero* signal — sampling changes, partial drops, one signal degraded while others continue — use
`partial-telemetry-loss.md` instead. For traces that arrive but are structurally broken, use
`trace-incompleteness.md`.

## Symptoms

- Metric series for a `service_name` stop updating or show gaps, without a matching deployment event.
- Traces for a service disappear from Tempo, or arrive with missing spans and broken parent links.
- Loki shows a log gap for a service that is still receiving traffic.
- Application logs contain OTLP or exporter errors: connection refused, deadline exceeded, queue full,
  dropped spans, retry exhausted.
- Collector or Alloy logs show export failures or backpressure.
- Dashboards look "green" simply because no data is arriving to be red.

A gap is an absence of evidence. It is not evidence of absence of failure.

## Signals to Check

**Mimir**
- Continuity of series such as `rpc_server_call_duration_count` and `http_server_request_duration_count`
  per `service_name`. A counter that stops increasing while traffic continues is a strong signal.
- Whether the gap affects one service, one node, or everything.
- Collector self-telemetry **if exported here** — examples to look for include exporter send-failed and
  queue-size metrics. Verify availability; do not assume the names.

**Loki**
- Application logs mentioning exporter, OTLP, gRPC status, or dropped telemetry.
- Alloy or collector pod logs for the same window.
- Whether log ingestion itself has a gap. A log gap plus a metric gap raises pipeline suspicion.

**Tempo**
- Whether traces exist but are incomplete (missing child spans) versus absent entirely.
- Broken `trace_id` continuity across services.

**Kubernetes (read-only)**
- Collector/Alloy pod status, restarts, OOMKills, CPU throttling, recent events.
- NetworkPolicy or Service endpoint changes affecting the OTLP endpoint.
- Whether the application pods themselves are running, ready, and serving.

## Investigation Steps

1. Establish the exact gap window per signal type (metrics, logs, traces). Check whether they align.
2. Determine blast radius: one service, one node, or all services. Cluster-wide gaps point to the
   pipeline; single-service gaps remain ambiguous.
3. Find **independent evidence the application is alive** — ingress or proxy metrics, another service's
   client-side spans calling it, or pod readiness. This is the decisive step.
4. Check application pod status and restart counts across the gap window.
5. Check collector/Alloy pod status: restarts, OOMKills, throttling, recent events.
6. Search application logs for exporter errors around the start of the gap.
7. Search collector logs for queue-full, refused-connection, or retry-exhausted messages.
8. Check whether telemetry resumed, and whether the resume time matches a collector restart.
9. Look for a deployment, config change, or NetworkPolicy change immediately before the gap.
10. Compare with a healthy baseline window using identical queries.

The agent must not restart the collector, patch pipeline config, or scale the pipeline.

## Possible Causes

**Observed evidence:** telemetry for one or more services is missing for a defined window.
**Inference:** either the service stopped producing telemetry, or the pipeline stopped accepting it.

Unverified hypotheses, each requiring its own supporting telemetry:

- **Collector or Alloy unavailable** — restarting or down, so exports fail cluster-wide.
- **Collector backpressure** — queues full under load, telemetry sampled away or dropped.
- **Collector resource pressure** — OOMKill or CPU throttling on the collector pods.
- **Network or policy change** — the OTLP endpoint is unreachable from application pods.
- **Application-side failure** — the service crashed, hung, or lost traffic, so there is genuinely
  nothing to export.
- **Configuration change** — endpoint, protocol, port, or TLS setting changed.
- **Backend ingestion limits** — Mimir, Loki, or Tempo rejecting writes on rate limits or cardinality.

## How to Distinguish Causes

**Application-side failure vs every pipeline hypothesis (the key split).** Find a signal that does **not**
pass through the suspect export path: proxy or ingress metrics, a caller's client-side span naming the
service, or Kubernetes pod readiness. If independent evidence shows the service still served traffic
during the gap, application failure is weakened and a pipeline cause is supported. If no such independent
signal exists, this question cannot be resolved and both remain live. Next read-only check: query a
caller's client-side spans for the silent service in the gap window.

**Collector unavailability or resource pressure vs backpressure.** Collector restarts or OOMKills
overlapping the gap support unavailability or resource pressure. A gap with no restarts but with
queue-full log lines supports backpressure instead. Next read-only check: collector pod restart count and
termination reason, alongside a log search for queue and drop messages.

**Collector unavailability vs network or policy change.** If the collector is healthy and other pods
export fine while one namespace or node cannot reach it, a network or policy change is supported over
collector unavailability. Next read-only check: compare export success across namespaces and nodes.

**Configuration change.** Supported when a config or deployment change immediately precedes the gap. A gap
with no corresponding change event weakens it. Next read-only check: ConfigMap and deployment revision
timestamps against the gap start.

**Backend ingestion limits.** Supported by rejection errors mentioning limits, quotas, or cardinality in
exporter logs — the pipeline is reachable but the backend is refusing writes. Next read-only check: search
exporter logs for 429 or limit-related rejection messages.

**Scope test.** A cluster-wide gap points to pipeline-level causes (collector, network, backend limits). A
single-service gap keeps application failure and per-service configuration alive.

## Recommended Actions

### Immediate Investigation
- Document the gap window separately for metrics, logs, and traces.
- Find and record at least one independent signal showing whether the application was serving.
- Collect exporter and collector error lines with timestamps.

### Potential Remediation
For human operator review only, and only where evidence supports the matching hypothesis:
- If collector resource pressure is evidenced, an operator may review collector limits and replicas.
- If a config or network change is evidenced, an operator may review that change.
- If backend ingestion limits are evidenced, an operator may review quotas and cardinality.

### Prevention
- Alert on **absence of expected telemetry** (stale counters), not only on error rates.
- Export collector self-telemetry so pipeline health is observable independently of the pipeline.
- Add a heartbeat or synthetic signal per service to distinguish "silent service" from "silent pipeline".
- Capacity-plan collector CPU, memory, and queue depth.

## Escalation / Unknowns

Escalate when there is no signal path independent of the failing exporter, when collector logs are not
collected, or when the gap predates available retention. In those cases the application-versus-pipeline
question cannot be resolved from telemetry alone, and the agent must report that explicitly rather than
choose a side.

Most important for this runbook: **missing telemetry is not evidence that nothing failed.** A gap may hide
a real incident. Retrieved logs may also be bounded by a query limit, so an empty result set is not proof
of an empty window. Any conclusion drawn during a telemetry gap should be reported with explicitly reduced
confidence.

## Correlation Guidance

**Metrics → Metrics:** a counter that stops increasing while an independent counter on the same request
path keeps rising isolates the failure to the export path rather than the application.

**Kubernetes → Application Telemetry:** collector restarts or OOMKills whose timing brackets the gap
explain the missing data. They do not prove the application was healthy during the gap.

**Logs → Metrics:** exporter error lines with timestamps should align with the start of the metric gap. A
misaligned start time suggests a different cause.

**Traces → Traces:** if a caller's client-side span for the silent service still exists, the service was
reached and responded, which is independent evidence that the application was alive.

**Metrics → Kubernetes:** telemetry resuming at the same moment a collector pod became ready supports a
collector cause over an application cause.

## Evidence Safety Rules

- **Missing telemetry means uncertainty, never "no failure occurred."** This is the governing rule for
  this runbook.
- Empty query results are not automatically equivalent to zero. Distinguish "no data collected" from
  "value was zero".
- Bounded log retrieval is a **sample** unless completeness is known.
- Correlation is not proof of causation. A collector restart overlapping the gap does not by itself
  establish the restart as the cause.
- A flat dashboard is not a healthy dashboard. Absence of red is not presence of green.
- Any conclusion reached during a telemetry gap must carry explicitly reduced confidence, and the agent
  should name which hypotheses could not be tested.
- Prefer the next read-only query that finds a signal path independent of the suspect exporter.