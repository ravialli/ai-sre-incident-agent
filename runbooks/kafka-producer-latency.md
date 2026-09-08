---
title: Kafka Producer Latency
category: messaging
services:
  - checkout
technologies:
  - kafka
  - opentelemetry
  - tempo
  - loki
  - mimir
  - kubernetes
severity: medium-high
read_only: true
related:
  - checkout-high-latency.md
  - frontend-timeout.md
  - downstream-dependency-failure.md
---

# Kafka Producer Latency

> **Demo runbook** for the `ai-sre-incident-agent` project. Not production-authoritative.
> All steps are **read-only**. Configuration and broker changes are recommendations for a human operator only.

## Purpose

Covers incidents where a producing service (commonly `checkout`, via an `orders publish` span) waits
seconds or tens of seconds for a Kafka write to be acknowledged, while the write eventually **succeeds**.
The goal is to separate broker-side, network, storage, and client-side explanations rather than defaulting
to "Kafka is slow". Retrieve this runbook when a messaging publish span dominates a slow trace.

## Symptoms

- A publish span (e.g. `orders publish`) dominates the parent trace duration in Tempo.
- Producer logs report long but successful writes, e.g. `Successful to write message. duration: 22.1s`.
- Caller RPC latency rises while `rpc_response_status_code="OK"` — no error signal.
- Latency may be bursty, or affect only some partitions or message keys.
- Upstream proxies may time out before the producer finishes.

A slow publish span shows where the time went. It does not identify why.

## Signals to Check

**Traces (Tempo)**
- Publish span duration distribution; whether the span is a leaf or has children.
- Span attributes for messaging system, topic, and partition, where instrumented.
- Multiple `trace_id` samples across the window, not one outlier.

**Logs (Loki)**
- Producer-side logs for the correlated `trace_id` / `span_id`: write durations, retries, metadata refresh
  messages, `batch expired`, `buffer full`, broker disconnects.
- Broker logs if collected: ISR shrink/expand, leader election, log flush warnings, request queue warnings.

**Metrics (Mimir)**
- Caller-side `rpc_server_call_duration_*` to establish blast radius.
- Kafka client and broker metrics **if exported in this environment** — verify before using. Examples to
  look for: producer request latency, record queue / buffer-available time, broker produce request total
  time, ISR shrink rate, under-replicated partitions, log flush time, request handler idle ratio. Treat
  these as examples, not guaranteed series names.

**Kubernetes (read-only)**
- Broker pod status, restarts, recent events, CPU throttling, memory pressure.
- PersistentVolume capacity and node disk pressure conditions.

## Investigation Steps

1. Confirm the wait is on acknowledgement, not on application code, by checking that the publish span is
   a leaf or ends with the broker response.
2. Sample several slow traces. Determine whether slowness is continuous or spiky.
3. Correlate each slow `trace_id` with producer logs. Look for retries or metadata refresh immediately
   before the slow write — those change the interpretation entirely.
4. Check broker pod health: restarts, throttling, evictions, recent scheduling events.
5. Check disk and volume utilisation, plus node disk pressure, for broker pods.
6. If broker metrics exist, compare produce request latency and under-replicated partitions against a
   quiet window.
7. Check whether slowness is partition- or topic-scoped. One hot partition behaves differently from a
   cluster-wide problem.
8. Review producer configuration as **read-only text** (deployment env vars, ConfigMaps): `acks`,
   `linger.ms`, `batch.size`, `buffer.memory`, `max.block.ms`,
   `max.in.flight.requests.per.connection`, `delivery.timeout.ms`, `compression.type`.
9. Compare identical queries across the incident window and a healthy baseline window.
10. Record consumer lag if visible, but do **not** treat it as a cause of producer latency.

The agent must not change Kafka configuration, scale brokers, restart pods, or modify ConfigMaps.

## Possible Causes

**Observed evidence:** the producer waits tens of seconds and then reports success.
**Inference:** the acknowledgement path — not message construction — is the bottleneck.

Unverified hypotheses, each requiring its own supporting telemetry:

- **Broker request latency** — brokers CPU-saturated or request queues deep.
- **ISR / replication delay** — with `acks=all`, a slow or shrinking in-sync replica set delays the ack.
- **Storage pressure** — slow disks, full volumes, or long log flush times.
- **Network latency or packet loss** between the producer pod and the brokers.
- **Producer configuration** — large `linger.ms`, or a high `delivery.timeout.ms` masking silent retries.
- **Metadata refresh or leader election** — the producer blocks while resolving a new partition leader.
- **Client-side buffer exhaustion** — `max.block.ms` waits caused by a full producer buffer.

**Explicitly not assumed:** consumer lag does not directly cause producer acknowledgement latency. Both
can rise from a shared broker constraint — that is correlation, not causation.

## How to Distinguish Causes

**Broker request latency vs storage pressure.** Broker CPU high with normal disk metrics supports broker
request latency. Normal broker CPU alongside high log flush time or node disk pressure supports storage
pressure. Next read-only check: compare broker container CPU against volume utilisation and flush-time
metrics over the same window.

**ISR / replication delay.** Supported by ISR shrink/expand events or under-replicated partitions
overlapping the slow window, combined with `acks=all` in the producer config. Absence of ISR churn during
the window weakens it substantially. Next read-only check: under-replicated partition count, plus a
config read for the `acks` value.

**Network path vs broker-side latency.** If client-observed latency is uniform across all topics and
partitions while broker-observed request time is *low*, the gap between the two measurements points to
the network path. If broker-side request time is also high, the network hypothesis weakens. Next
read-only check: compare client publish-span duration against broker produce-request latency for the
same window. See `dns-or-network-failure.md` before concluding "network".

**Producer configuration vs client buffer exhaustion.** `linger.ms` effects are small and constant —
milliseconds, not tens of seconds — so linger alone cannot explain a 22-second wait. Long waits
accompanied by `buffer full` or `max.block.ms` log lines support buffer exhaustion instead. Next
read-only check: search producer logs for buffer and block messages around a known slow `trace_id`.

**Metadata refresh / leader election.** Supported when metadata refresh or leader-change log lines appear
immediately before slow writes. Their absence weakens it. Next read-only check: producer log search for
metadata and leader messages, time-aligned to slow spans.

**Cluster-wide vs partition-scoped.** If only one partition is slow, cluster-wide hypotheses (broker CPU,
storage, network) weaken and partition-scoped ones (ISR, leader election, hot key skew) strengthen. Next
read-only check: group publish-span duration by the partition attribute, where instrumented.

## Recommended Actions

### Immediate Investigation
- Collect trace, log, and metric evidence tied to specific `trace_id` values.
- Establish whether the problem is cluster-wide, topic-scoped, or partition-scoped.
- Compare against a baseline window using identical queries.

### Potential Remediation
For human operator review only, and only where evidence supports the matching hypothesis:
- If ISR churn is evidenced, an operator may review replication settings and broker health.
- If storage pressure is evidenced, an operator may review volume capacity and disk IO.
- If client blocking is evidenced, an operator may review producer buffer and timeout settings.

### Prevention
- Export Kafka client and broker metrics into Mimir if they are absent today.
- Set bounded producer timeouts so callers fail fast rather than exceeding upstream deadlines.
- Alert on publish-span duration, not just error rate.
- Capacity-plan broker CPU, disk throughput, and partition counts.

## Escalation / Unknowns

Escalate when broker-side telemetry is unavailable, when producer configuration cannot be read, or when
partition-level attributes are missing from spans. State clearly which hypotheses could not be tested and
why.

If logs return no errors, retrieved logs may be **bounded by a query limit**. Absence of ERROR or WARN in
the sample is not proof of absence in the window. Missing telemetry must reduce confidence rather than
support a "no failure" conclusion.

## Correlation Guidance

**Traces → Logs:** a slow publish span's `trace_id` queried in Loki should surface the producer's own
duration line. Agreement between the two strengthens confidence that the broker wait is real.

**Logs → Logs:** producer retry or metadata-refresh lines immediately preceding a slow write reframe the
incident from "broker slow" to "client re-resolving the cluster".

**Metrics → Metrics:** client-observed publish latency far exceeding broker-reported produce latency
isolates the gap to the network or client path rather than the broker.

**Kubernetes → Application Telemetry:** broker pod restarts or disk pressure overlapping the slow window
are correlated evidence. Correlation alone does not establish the pod condition as the root cause.

## Evidence Safety Rules

- Correlation is not proof of causation. Consumer lag rising alongside producer latency does not mean one
  caused the other; a shared broker constraint can produce both.
- A slow downstream publish span may be a symptom of a deeper broker, storage, or network condition.
- Bounded log retrieval is a **sample** unless completeness is known. An empty result is not zero.
- Histogram bucket ceilings are not exact latency measurements.
- Compare multiple traces before generalising. One slow trace is an anecdote, not a pattern.
- Missing broker telemetry means uncertainty about broker health, not evidence that brokers are healthy.
- Tie every recommendation to observed evidence, or label it explicitly as a hypothesis.
- Prefer the next read-only query that separates competing hypotheses.