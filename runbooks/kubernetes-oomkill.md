---
title: Kubernetes OOMKilled
category: resources
services:
  - recommendation
  - ad
  - cart
  - checkout
technologies:
  - kubernetes
  - mimir
  - loki
severity: high
read_only: true
---

# Kubernetes OOMKilled

## Purpose
Covers OpenTelemetry Demo containers terminated by the kernel OOM killer (reason `OOMKilled`, exit code 137). The demo's `recommendationServiceCacheFailure` flag can drive this in `recommendation` — it is documented as "Create a memory leak due to an exponentially growing cache. 1.4x growth, 50% of requests trigger growth." Retrieve when memory nears the container limit or the termination reason is `OOMKilled`. Distinguish container-limit OOM from node-level OOM, and OOM from generic CPU-driven slowness.

## Symptoms
- Metrics: `container_memory_working_set_bytes` approaching `kube_pod_container_resource_limits{resource="memory"}`; restarts with reason `OOMKilled`.
- Logs: allocation failures; abrupt termination with no graceful shutdown.
- Traces: telemetry stops at the kill instant.
- Kubernetes: `Last State: Terminated, Reason: OOMKilled, Exit Code: 137`; node MemoryPressure events for node-level OOM.

## Signals to Check
### Metrics — memory usage vs limit, restart counts, saturation
Working set vs limit: `container_memory_working_set_bytes{namespace="otel-demo", pod=~"recommendation.*"} / on(pod,container,namespace) kube_pod_container_resource_limits{resource="memory"}`. Use working set, not `container_memory_usage_bytes` (which includes reclaimable page cache).
### Logs — OOM/allocation messages
`{namespace="otel-demo", service_name="recommendation"} |~ "memory|alloc"`.
### Traces — memory-growth correlation
Correlate the growth window with request patterns (e.g. flag-triggered cache growth).
### Kubernetes — termination reason, node pressure
`kube_pod_container_status_last_terminated_reason{namespace="otel-demo", reason="OOMKilled"}`; `kube_node_status_condition{condition="MemoryPressure", status="true"}`.

## Investigation Steps
1. Confirm reason `OOMKilled`/exit 137 via the last-terminated-reason metric and pod describe.
2. Plot the working-set trajectory approaching the limit; note the growth rate (steady leak vs spike).
3. Determine container-limit OOM vs node-level OOM: node MemoryPressure and several pods killed together suggests node-level.
4. Check whether `recommendationServiceCacheFailure` (or a similar flag) is enabled.
5. Correlate growth with load. Read-only; limit changes are human recommendations.

## Possible Causes
- Memory leak — observed: monotonic working-set growth to the limit (e.g. the recommendation cache).
- Under-provisioned limit — observed: steady usage that legitimately exceeds a low limit.
- Load spike — observed: growth tracks request rate.
- Node-level memory exhaustion — observed: node MemoryPressure, several pods killed.

## How to Distinguish Causes
- **Leak vs undersized limit.** Supported for a leak by continuous growth without a plateau across restarts; for undersized by stable-but-high usage that simply exceeds a low ceiling. Next: `quantile_over_time(0.95, container_memory_working_set_bytes{pod=~"recommendation.*"}[6h])`.
- **Container-limit vs node-level OOM.** Supported for node-level by `kube_node_status_condition{condition="MemoryPressure"}=1` and co-located pods dying; weakened if only one container on a healthy node. Next: query the node condition and per-node OOM events.
- **Flag-induced vs organic.** Supported if the cache-failure flag is enabled in flagd. Next: read flagd config.

## Recommended Actions
### Immediate Investigation
Confirm the OOM reason; chart working set vs limit; separate node-level from container-level; check the feature flag.
### Potential Remediation
A human operator may consider raising memory limits/requests, fixing the leak, disabling the fault flag, or rescheduling off a pressured node, once confirmed.
### Prevention
Alert when working set approaches the configured memory limit (a warning band below the limit); memory profiling (Pyroscope); right-size requests/limits; leak tests in CI.

## Escalation / Unknowns
If memory metrics are sparse near the kill, the trajectory may be incomplete — escalate with the observed reason. Missing metrics reduce confidence; they do not prove memory was fine.

## Correlation Guidance
Metrics → Kubernetes: working set nearing the limit precedes the `OOMKilled` reason. Kubernetes → Application Telemetry: the kill explains the telemetry gap; the gap does not explain the kill. Metrics → Traces: growth correlated to specific request types suggests the leaking code path.

## Evidence Safety Rules
Use working set, not usage-with-cache, to judge OOM risk. Exit 137 is strongly but not exclusively OOM — verify the reason string. Correlation of load and memory is not proof of a leak. Empty metrics near the kill mean uncertainty.