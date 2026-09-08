---
title: Checkout High Latency
category: latency
services:
  - checkout
  - frontend
  - frontend-proxy
technologies:
  - opentelemetry
  - kafka
  - tempo
  - loki
  - mimir
  - kubernetes
severity: high
read_only: true
related:
  - kafka-producer-latency.md
  - frontend-timeout.md
  - cpu-saturation.md
  - downstream-dependency-failure.md
---

# Checkout High Latency

> **Demo runbook** for the `ai-sre-incident-agent` project. Not production-authoritative.
> All steps are **read-only**. Any change must be recommended to a human operator, never performed by the agent.

## Purpose

Covers incidents where `checkout` request duration rises sharply (seconds to tens of seconds) while the
RPC error rate stays at or near zero. This pattern usually means requests are *waiting*, not *failing*,
and the wait is often inherited from a downstream dependency. Retrieve this runbook for checkout latency
with a flat error rate. For checkout latency **with** rising errors, prefer `high-error-rate.md`.

## Symptoms

- p95/p99 of `rpc_server_call_duration_*` for `service_name="checkout"` jumps from sub-second to many seconds.
- `rpc_response_status_code="OK"` accounts for nearly all calls; error ratio stays ~0%.
- Tempo traces for `oteldemo.CheckoutService/PlaceOrder` show total durations in the tens of seconds.
- Most of the trace duration sits in one child span (commonly `orders publish`), not spread evenly.
- Upstream `frontend` or `frontend-proxy` may report timeouts even though checkout eventually succeeds.
- Checkout logs contain slow-but-successful entries, e.g. `Successful to write message. duration: 22.1s`.

Symptoms alone do not establish a cause. Slow-and-successful is a shape, not a diagnosis.

## Signals to Check

**Mimir metrics**
- `rpc_server_call_duration_bucket`, `_count`, `_sum` for `service_name="checkout"`, grouped by
  `rpc_method` and `rpc_response_status_code`. Verify these exact series and label names exist in this
  environment before relying on them.
- Rate of `rpc_server_call_duration_count` to confirm whether traffic volume changed.
- `http_server_request_duration_*` for `frontend` to see how the symptom appears upstream.
- Container CPU, memory, and CFS throttling series for the checkout pods.

**Tempo traces**
- Slowest `oteldemo.CheckoutService/PlaceOrder` traces in the incident window.
- Child span breakdown: which `span_id` holds the bulk of the duration, and whether that span has
  downstream children or is a leaf.
- Compare a slow trace against a fast trace from the same window.

**Loki logs**
- `service_name="checkout"` around a known slow `trace_id`.
- Duration-bearing log lines, plus ERROR/WARN entries.

**Kubernetes (read-only)**
- Pod status, restart counts, recent events, resource requests/limits, node pressure conditions.

## Investigation Steps

1. Confirm the latency shape from `rpc_server_call_duration_bucket`. Compute p95/p99 and also compare
   `_sum` / `_count` (mean). If the mean is high too, most requests are slow, not just a tail.
2. **Check the top histogram bucket.** If p95/p99 lands on the 10s bucket boundary, treat it as
   "≥ 10s, unbounded" — not "exactly 10s". Use traces or `_sum`/`_count` for real magnitude.
3. Confirm error rate separately, grouped by `rpc_response_status_code`. Latency-without-errors and
   latency-with-errors are different incidents.
4. Check whether request rate rose at the same time. Flat traffic with rising latency points away from
   simple load saturation.
5. Pull 3–5 of the slowest traces from Tempo. Record `trace_id` values for log correlation.
6. Identify the dominant child span. Note whether the slow span represents an external call
   (e.g. `orders publish` → Kafka) or local work.
7. Query Loki for those `trace_id` values. Compare the emitted write duration against the span duration.
   Matching durations support "the wait is real, not instrumentation error".
8. Compare a quiet window before the incident using identical queries. Same query, two windows.
9. Check checkout pod health: restarts, CPU throttling, memory pressure, recent scheduling events.
10. If the dominant span is a messaging publish, hand off to `kafka-producer-latency.md`.

The agent must not restart pods, scale checkout, or alter configuration. Changes are operator recommendations.

## Possible Causes

**Observed evidence:** latency concentrated in a single downstream publish span while RPC status is `OK`.
**Inference:** checkout is blocked waiting on a downstream acknowledgement rather than failing.

Unverified hypotheses, each requiring its own telemetry before it can be asserted:

- **Downstream messaging delay** — the Kafka producer path is slow to acknowledge writes.
- **Checkout resource pressure** — CPU throttling, memory pressure, or GC pauses inside the checkout pod.
- **A different downstream gRPC dependency** is slow and the publish span is coincidental.
- **Load-driven concurrency saturation** — traffic increase pushed checkout past its concurrency limits.
- **Instrumentation or clock-skew artifact** — the measured latency overstates the real wait.

## How to Distinguish Causes

**Downstream messaging delay vs checkout resource pressure.** Messaging delay is supported when the slow
span is a leaf waiting on an external system while checkout CPU, memory, and throttling are normal.
Resource pressure is supported when checkout shows sustained CFS throttling, memory near its limit, or
restarts — keep it alive even if a publish span looks slow, because a throttled process also produces
long spans. Next read-only check: container CPU throttling rate for checkout pods across the same window.

**Downstream messaging delay vs a different gRPC dependency.** Sum per-span durations by span name across
several slow traces. If the publish span dominates while other downstream spans stay flat, the alternative
dependency is weakened. If two downstream spans grew together, suspect a shared constraint instead.
Next read-only check: per-span-name duration breakdown across 5 slow traces, not one.

**Downstream messaging delay vs load-driven saturation.** Compare `rate(rpc_server_call_duration_count)`
before and during the window. Flat request rate weakens the saturation hypothesis. Rising rate alongside
rising latency keeps it alive but does not confirm it — load and latency can both be downstream effects.

**Real wait vs instrumentation artifact.** If application logs independently report a duration close to
the span duration (`duration: 22.1s`), the artifact hypothesis is weakened, because two independent
sources agree. If only the span is long and no log corroborates it, keep the artifact hypothesis open.

**Whole-service vs single-endpoint.** Group latency by `rpc_method`. One slow method points to a specific
downstream dependency; all methods slow points to the pod, node, or a shared dependency.

## Recommended Actions

### Immediate Investigation
- Capture representative `trace_id` values, span breakdowns, and matching log lines as evidence.
- Record before/during metric comparisons using identical queries.
- Determine whether the slow span is inside checkout or in a downstream dependency.

### Potential Remediation
For human operator review only, and only if evidence supports the matching hypothesis:
- If evidence points to the messaging path, an operator may review broker health and producer settings.
- If checkout shows resource pressure, an operator may review requests/limits and replica count.

### Prevention
- Add histogram buckets above 10s so extreme latency is measurable rather than clipped.
- Review timeouts and deadlines on the checkout publish path so requests fail fast instead of hanging
  past upstream deadlines.
- Alert on publish-span duration, not only on error rate.

## Escalation / Unknowns

Escalate to a human when the dominant span has no child spans and no downstream instrumentation exists,
when broker-side telemetry is unavailable, or when trace sampling is too sparse to find slow examples.
State explicitly which hypotheses could not be tested.

Missing telemetry is not evidence of health. If Loki returns no ERROR lines, results may be bounded by a
query limit — absence in the sample does not prove absence in the window. Missing or truncated signals
must **lower confidence**, never be reported as proof that nothing failed.

## Correlation Guidance

**Metrics → Traces:** a p95 rise in `rpc_server_call_duration_*` defines the window from which to pull the
slowest `PlaceOrder` traces.

**Traces → Logs:** a slow trace's `trace_id` queried in Loki should surface a checkout log line with a
comparable duration. Agreement between span duration and logged duration strengthens confidence that the
wait is real.

**Traces → Metrics:** the dominant child span names the next dependency to query. A dominant `orders publish`
span directs the investigation to Kafka producer metrics, not to checkout CPU.

**Kubernetes → Application Telemetry:** checkout restarts or throttling overlapping the latency window are
correlated evidence only. Correlation does not establish the pod condition as the root cause.

## Evidence Safety Rules

- Correlation is not proof of causation. A slow publish span co-occurring with checkout latency does not
  prove the publish path caused it.
- **Histogram bucket ceilings are not exact latency measurements.** A p99 sitting on the 10s bucket means
  "≥ 10s", and the true value may be far higher.
- The slowest span is not automatically the ultimate root cause; it may itself be waiting on something deeper.
- A trace can overlap the incident window even if its root span started before the window began.
- Bounded Loki results are a **sample**. An empty result set is not equivalent to zero occurrences.
- A downstream span that is slow or failing may be a symptom rather than the originating cause.
- Every recommendation must be tied to observed evidence or explicitly labeled as a hypothesis.
- Prefer the next query that separates two competing hypotheses over one that merely adds support to the
  currently favoured one.