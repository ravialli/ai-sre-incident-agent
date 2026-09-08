---
title: Trace Incompleteness
category: observability
services:
  - frontend
  - checkout
  - payment
  - cart
  - product-catalog
technologies:
  - opentelemetry
  - tempo
  - alloy
  - kafka
severity: medium
read_only: true
---

# Trace Incompleteness

## Purpose
Covers distributed traces in the OpenTelemetry Demo that are missing spans, missing a root span, or broken across service boundaries — e.g. a `checkout` trace with no `payment` child, or context not propagated through Kafka between `checkout` and `fraud-detection`. Retrieve when traces look truncated. Incomplete traces reduce confidence; an absent span is not proof the work did not happen.

## Symptoms
- Traces: missing root (`trace:rootName` empty); orphan spans without parents; an expected downstream span absent; span count lower than the call graph implies.
- Metrics: a caller shows a request that the callee's spans do not reflect.
- Logs: a `trace_id` present in a service's logs while that service's spans are absent in Tempo.
- Kubernetes: Alloy/collector restarts during the window.

## Signals to Check
### Traces — root presence, parent/child, span coverage
`{ trace:rootName = "" }` to find rootless traces; inspect a suspect trace's span tree for gaps.
### Metrics — caller vs callee span presence
Compare request/RPC counts to span volume per service.
### Logs — trace_id without matching spans
`{namespace="otel-demo", service_name="payment"} | json | trace_id != ""` then look up the trace.
### Kubernetes — collector health
Alloy restarts/queue during the window.

## Investigation Steps
1. Confirm the trace is genuinely incomplete vs merely still in flight or sampled.
2. Identify where the tree breaks: which service's span is missing and whether its parent exists.
3. Check context propagation across boundaries — async hops through Kafka (`checkout`→queue→`fraud-detection`) commonly break links unless context is propagated.
4. Correlate with collector/Alloy health and sampling (tail sampling can drop parts when late spans arrive after the decision window).
5. Cross-check the missing service's logs by `trace_id` to see whether it processed the request. Read-only.

## Possible Causes
- Context-propagation gap — observed: an async/Kafka hop with no linked span; an instrumentation boundary.
- Sampling/late-span drop — observed: a tail-sampling decision window shorter than the trace duration.
- Collector drop of some spans — observed: Alloy queue full/restart.
- Instrumentation gap in a service — observed: the service is present in metrics/logs but emits no spans.

## How to Distinguish Causes
- **Propagation vs drop.** Supported for a propagation gap when the boundary is async and the downstream logs the `trace_id` but as a new/root trace; for a drop when spans exist elsewhere but Alloy shows losses. Next: check the async hop and collector self-metrics.
- **Sampling vs loss.** Supported for sampling when only late-arriving spans are missing and no collector errors exist; weakened if the collector reports drops. Next: review the tail-sampling `decision_wait`.
- **Instrumentation gap vs transport loss.** Supported for an instrumentation gap when the service never emits spans in any trace; for transport loss when it usually does. Next: check the service's historical span coverage.

## Recommended Actions
### Immediate Investigation
Locate the tree break; verify propagation across async hops; check the sampling window and collector health; cross-check logs by `trace_id`.
### Potential Remediation
A human operator may consider fixing propagation/instrumentation, lengthening the sampling decision window, or scaling the collector, once confirmed.
### Prevention
Trace-coverage checks per service; propagation tests across Kafka/HTTP/gRPC; monitor collector drops; document sampling behavior.

## Escalation / Unknowns
An incomplete trace limits root-cause certainty — use metrics/logs to compensate and escalate if a critical path is unobservable. A missing span is uncertainty, not evidence the operation was skipped.

## Correlation Guidance
Logs → Traces: a `trace_id` in a service's logs whose spans are absent pinpoints where the trace broke. Metrics → Traces: caller request counts exceeding callee span counts flag missing spans. Kubernetes → Traces: collector restarts explain gaps but do not prove the work failed.

## Evidence Safety Rules
A trace can overlap the incident window even if its root started before it. Absent spans are not proof of skipped work. Bounded/sampled traces are samples — compare several before concluding. Empty results are not zero.