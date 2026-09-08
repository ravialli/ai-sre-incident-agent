---
title: Frontend Timeout
category: latency
services:
  - frontend
  - frontend-proxy
  - checkout
technologies:
  - envoy
  - opentelemetry
  - tempo
  - loki
  - mimir
  - kubernetes
severity: high
read_only: true
related:
  - checkout-high-latency.md
  - kafka-producer-latency.md
  - service-unavailable.md
  - http-service-latency.md
---

# Frontend Timeout

> **Demo runbook** for the `ai-sre-incident-agent` project. Not production-authoritative.
> All steps are **read-only**. Timeout or config changes are recommendations for a human operator only.

## Purpose

Covers incidents where users or the `frontend` / `frontend-proxy` see failed or timed-out requests, while
backend services may still be completing the work successfully — just too slowly. The core task is to
separate **backend slowness** from **proxy or client timeout configuration**. Retrieve this runbook when
user-facing failures coexist with healthy-looking backend dashboards.

## Symptoms

- `http_server_request_duration_*` for `service_name="frontend"` shows a cluster of requests ending at a
  suspiciously uniform duration (e.g. almost exactly 5s, 10s, or 15s).
- Increase in 5xx (often 504) or client-cancelled responses at the proxy.
- Tempo traces where the client or proxy span ends **before** the server span completes.
- The backend service (e.g. `checkout`) reports `rpc_response_status_code="OK"` for the same operations.
- Users report failures while backend dashboards show no errors.

A timeout is a client-side decision. It shows when the caller gave up, not why the callee was slow.

## Signals to Check

**Metrics (Mimir)**
- `http_server_request_duration_bucket`, `_count`, `_sum` for `service_name="frontend"`, grouped by route
  and status code. Verify these series and label names exist in this environment.
- The same series for `frontend-proxy` if instrumented.
- `rpc_server_call_duration_*` for the backend service the failing route calls.
- Ratio of error status codes to total requests, before and during the incident.

**Traces (Tempo)**
- Traces containing both the proxy/client span and the backend server span under one `trace_id`.
- Client span duration vs server span duration — the mismatch is the key evidence.
- Spans marked cancelled, aborted, or ending mid-flight.

**Logs (Loki)**
- Proxy access logs: response code, upstream response flags, request duration.
- Frontend logs for cancelled or aborted request messages.
- Backend logs for the same `trace_id` showing work continued after the client left.

**Configuration (read-only)**
- Proxy/Envoy route timeouts, idle timeouts, and retry policy.
- Client-side HTTP timeouts in the frontend.
- Ingress or load balancer timeouts.

## Investigation Steps

1. Identify affected routes from `http_server_request_duration_*` grouped by route and status code.
2. Check the duration distribution. **A tight cluster at a round number strongly suggests a configured
   timeout**, not natural latency.
3. Confirm whether that timing value matches any timeout in the proxy, ingress, or client config.
4. Pull traces for failing requests. Record `trace_id` values and compare span end times across services.
5. Determine whether the backend span **completed successfully after** the client span ended. If so, the
   backend was slow but not broken.
6. Check the backend's own latency series. Note whether p95/p99 sits at the top histogram bucket — a 10s
   bucket ceiling means "≥ 10s", not "exactly 10s".
7. Check whether backend latency rose *before* frontend timeouts began. Order of onset matters.
8. Check whether proxy config changed recently (deployment or rollout events, ConfigMap revisions).
9. Check retry policy. Retries can multiply load and turn a mild slowdown into a visible outage.
10. Compare an identical query against a healthy baseline window.

The agent must not edit proxy config, restart pods, or scale workloads.

## Possible Causes

**Observed evidence:** frontend requests fail at a consistent duration; backend spans complete later with
success status.
**Inference:** the client or proxy is giving up before the backend finishes.

Unverified hypotheses, each requiring its own supporting telemetry:

- **Backend slowness** — a downstream dependency (e.g. a messaging publish) is blocking the backend.
- **Timeout set too short** — the configured timeout is below normal p99 for this route.
- **Recent config change** — a timeout or retry setting was reduced or newly introduced.
- **Retry amplification** — retries on timeout increase backend load and worsen latency.
- **Idle or connection timeout** — connections closed by an idle timeout rather than a request timeout,
  producing similar symptoms with different proxy log flags.
- **Proxy or frontend layer capacity** — the failure originates at the proxy tier, not the backend.

## How to Distinguish Causes

**Backend slowness vs timeout set too short (the primary split).** If the backend span *completed
successfully* after the client gave up, then the backend is slow **and** the timeout is a contributing
factor — both are true simultaneously, and the fix depends on which is more out of line. If the backend
span never completed or ended in error, backend slowness dominates and the timeout is secondary. Next
read-only check: for one `trace_id`, compare client span end time against server span end time and status.

**Timeout set too short vs recent config change.** If the timeout value has been stable historically while
backend latency just rose, a static-timeout explanation is weak on its own. If the timeout duration
changed recently and backend latency is unchanged, the config change is supported. Next read-only check:
review proxy config revision history against the incident onset time.

**Backend slowness vs retry amplification.** Compare backend request rate. If backend
`rpc_server_call_duration_count` rose sharply while user-facing traffic stayed flat, retries are
amplifying load and retry amplification is supported. Matching rates weaken it. Next read-only check:
plot frontend request rate and backend request rate on the same window.

**Request timeout vs idle or connection timeout.** These produce different proxy response flags. Read the
flags in the access logs rather than inferring the cause from duration alone. Next read-only check: group
proxy access log lines by upstream response flag.

**Backend slowness vs proxy-tier capacity.** If backend latency is normal while the proxy or frontend pods
show CPU throttling, restarts, or saturation, the proxy tier strengthens as the origin. Next read-only
check: container CPU throttling and restart counts for `frontend` and `frontend-proxy` pods.

**Blast radius test.** One route affected favours a specific downstream dependency. All routes affected
favours a proxy-layer or platform-level cause.

## Recommended Actions

### Immediate Investigation
- Capture matched pairs of client-span and server-span durations for the same `trace_id`.
- Record the exact timeout value observed in the duration distribution and in configuration.
- Establish whether the backend eventually succeeded.

### Potential Remediation
For human operator review only, and only where evidence supports the matching hypothesis:
- If the backend is genuinely slow, an operator may investigate that dependency (see
  `checkout-high-latency.md` and `kafka-producer-latency.md`) rather than raising timeouts.
- If timeout configuration is misaligned with realistic p99, an operator may review the value. Raising a
  timeout hides symptoms and may increase resource consumption.
- If retries are amplifying load, an operator may review retry and backoff policy.

### Prevention
- Align timeouts consistently across client, proxy, and backend so the innermost deadline fires first.
- Alert on client-vs-server span duration mismatch, which detects this pattern directly.
- Add higher histogram buckets so extreme backend latency is measurable rather than clipped.
- Define route-level latency SLOs and set timeouts above realistic p99, not below it.

## Escalation / Unknowns

Escalate when proxy access logs or proxy spans are not collected, when trace context is not propagated end
to end, or when timeout configuration cannot be read. In those cases the backend-vs-timeout split cannot
be settled with the available evidence, and the agent should say so explicitly rather than pick a side.

Absence of proxy error logs may reflect a query limit or missing collection, not a healthy proxy. Treat
missing telemetry as **reduced confidence**, never as proof that no failure occurred.

## Correlation Guidance

**Metrics → Configuration:** a tight cluster of request durations at a round number should be matched
against the configured proxy, ingress, and client timeout values. A match is strong evidence the ceiling
is configured rather than natural.

**Traces → Traces:** within one `trace_id`, a client span ending before its server span is the defining
signature of this incident pattern. Neither span alone reveals it.

**Traces → Logs:** the backend log lines for a timed-out `trace_id` often show the work completing after
the caller disconnected, confirming the backend was slow rather than broken.

**Metrics → Metrics:** backend request rate rising while frontend request rate stays flat indicates retry
amplification rather than a genuine traffic increase.

**Kubernetes → Application Telemetry:** proxy pod restarts overlapping the timeout window are correlated
evidence only, and do not by themselves establish the restarts as the cause.

## Evidence Safety Rules

- Correlation is not proof of causation. A timeout coinciding with backend latency does not establish
  which one is the primary problem.
- A timeout is a client-side decision, not a measurement of backend health. Do not read 504s as proof the
  backend failed.
- Histogram bucket ceilings are not exact latency measurements; a p99 at the 10s bucket means "≥ 10s".
- Bounded proxy log retrieval is a **sample**. Empty results are not equivalent to zero errors.
- A trace can overlap the incident window even if its root span started before the window began.
- Not every timeout is a network problem. Confirm backend health before reaching for
  `dns-or-network-failure.md`.
- Recommendations must be tied to observed evidence or explicitly labelled as hypotheses.
- Prefer the next read-only query that separates backend slowness from timeout configuration.