---
title: Partial Telemetry Loss
category: observability
services:
  - checkout
  - frontend
  - recommendation
technologies:
  - opentelemetry
  - alloy
  - mimir
  - loki
  - tempo
severity: medium
read_only: true
---

# Partial Telemetry Loss

## Purpose
Covers gaps where some telemetry (metrics, logs, or traces) is missing or reduced for OpenTelemetry Demo services while the application may still be serving traffic — e.g. Grafana Alloy collector drops, exporter backpressure to Mimir/Loki/Tempo, or a single-signal pipeline degrading. Retrieve when a signal disappears. Missing telemetry must reduce confidence, not be read as "no failure occurred."

## Symptoms
- Metrics: a sudden drop in series count/ingest for a service; collector queue/drop counters rising.
- Logs: a gap in Loki volume for a service; Alloy exporter errors.
- Traces: reduced span volume; missing spans for a service that is still present in metrics.
- Kubernetes: Alloy pod restarts/pressure; OTLP export errors in the collector logs.

## Signals to Check
### Metrics — ingest/series volume, collector health
Series/ingest per service over time; Alloy/collector self-metrics (queue size, dropped/failed export counters).
### Logs — exporter/pipeline errors
`{namespace="otel-demo", service_name="alloy"} |= "export" |= "error"` (or the collector's own stream).
### Traces — reduced span volume vs baseline
Compare span counts per `resource.service.name` to a healthy window.
### Kubernetes — Alloy pod health
Restarts/resource pressure on the Alloy/collector pods.

## Investigation Steps
1. Determine which signal(s) dropped and for which services — one signal, one service, or cluster-wide.
2. Distinguish reduced traffic (all signals plus request metrics fall together) from telemetry loss (one signal drops while others persist).
3. Check Alloy/collector health, restarts, and queue/drop/failure counters.
4. Check whether sampling or config changed (head/tail sampling, filters).
5. Verify the application is still serving via an independent signal (e.g. Envoy metrics). Read-only.

## Possible Causes
- Collector/Alloy drop or restart — observed: exporter failures, queue full, Alloy restart.
- Exporter backpressure to Mimir/Loki/Tempo — observed: failed-export counters, 429/5xx from the backend.
- Sampling/config change — observed: a config diff reducing volume.
- Genuine traffic decrease — observed: request metrics also fell (then it is not telemetry loss).

## How to Distinguish Causes
- **Telemetry loss vs traffic drop.** Supported for loss when one signal falls while request-rate metrics and other signals hold; for a traffic drop when all signals and request rate fall together. Next: overlay request rate with span/log volume.
- **Collector vs backend.** Supported for collector by Alloy restarts/queue-full; for backend by export errors (429/5xx) toward Mimir/Loki/Tempo. Next: read the collector export logs/self-metrics.
- **Sampling vs failure.** Supported by a config change reducing volume without errors. Next: review sampling config (read-only).

## Recommended Actions
### Immediate Investigation
Localize the missing signal/service; compare against request rate; check collector health and export errors; review sampling config.
### Potential Remediation
A human operator may consider scaling/fixing Alloy, relieving backend backpressure, or reverting a sampling change, once confirmed.
### Prevention
Alert on collector drop/failure counters and per-service ingest; monitor pipeline health; capacity-plan the collector; document sampling.

## Escalation / Unknowns
While a signal is missing, the incident state for that service is uncertain — rely on the remaining signals and escalate if a critical service is dark. Absence of telemetry is not evidence of health.

## Correlation Guidance
Metrics → Logs: collector drop counters guide reading the collector export logs. Metrics → Metrics: steady request rate but reduced span volume isolates telemetry loss. Kubernetes → Application Telemetry: Alloy restarts explain gaps but do not confirm the app is fine.

## Evidence Safety Rules
Missing telemetry means uncertainty, never "no failure." Empty query results are not automatically zero. Bounded results are samples. A drop in one signal does not prove the others are complete. Base conclusions on the signals that remain plus explicit unknowns.