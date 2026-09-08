---
title: Memory Pressure
category: resources
services:
  - recommendation
  - cart
  - product-catalog
  - ad
technologies:
  - kubernetes
  - mimir
  - loki
severity: medium-high
read_only: true
---

# Memory Pressure

## Purpose
Covers rising memory usage and node MemoryPressure in the OpenTelemetry Demo that has not yet caused an OOM kill, including eviction risk. Retrieve when working-set memory trends upward or a node reports MemoryPressure. Memory pressure is a precursor state; distinguish it from a completed OOM kill (`kubernetes-oomkill.md`).

## Symptoms
- Metrics: `container_memory_working_set_bytes` trending toward the limit; node available memory falling.
- Logs: GC pressure; cache-eviction warnings.
- Traces: latency creep as GC/allocation pressure grows.
- Kubernetes: `kube_node_status_condition{condition="MemoryPressure"}=1`; pod evictions (`status.phase=Failed`, reason Evicted).

## Signals to Check
### Metrics — memory usage vs limit, node memory, saturation
Container: working-set-vs-limit ratio. Node: `kube_node_status_condition{condition="MemoryPressure", status="true"}`.
### Logs — GC/eviction messages
`{namespace="otel-demo"} |~ "evict|OutOfMemory|gc pause"`.
### Traces — latency creep during pressure
Compare p95 across the pressure window.
### Kubernetes — node conditions, evictions, requests/limits
`kube_pod_status_phase{namespace="otel-demo", phase="Failed"}`; resource requests/limits.

## Investigation Steps
1. Determine whether the pressure is per-container (approaching its own limit) or node-wide (node MemoryPressure).
2. Chart the growth trend and estimate time-to-limit.
3. Check for pod evictions and their messages (node low on memory).
4. Correlate with load and with any leak-inducing flag.
5. Compare requests vs limits vs actual usage to spot over-commit. Read-only.

## Possible Causes
- Gradual leak trending toward a future OOM — observed: monotonic growth.
- Node over-commit — observed: sum of usage near node capacity, MemoryPressure.
- Legitimate load growth — observed: usage tracks traffic.
- Undersized requests causing scheduling onto pressured nodes.

## How to Distinguish Causes
- **Container leak vs node over-commit.** Supported for a container leak by a single pod growing toward its limit; for node over-commit by many pods and node MemoryPressure. Next: compare per-pod working set to node available memory.
- **Leak vs load.** Supported for a leak if memory keeps rising while load is flat; for load if the two track. Next: overlay working set with request rate.
- **Eviction risk.** Supported when node MemoryPressure is true and QoS is Burstable/BestEffort. Next: inspect evicted-pod messages.

## Recommended Actions
### Immediate Investigation
Separate container vs node pressure; chart the trend and time-to-limit; check evictions; compare requests/limits/usage.
### Potential Remediation
A human operator may consider right-sizing requests/limits, fixing a leak, rescheduling, or adding node capacity, once confirmed.
### Prevention
Early-warning alerts well below the limit; capacity planning with headroom; profiling; correct QoS via requests.

## Escalation / Unknowns
If node-level metrics are missing, node-vs-container attribution is uncertain — escalate with what is observed. Absence of evictions does not prove there is no pressure if metrics are incomplete.

## Correlation Guidance
Metrics → Kubernetes: rising working set precedes MemoryPressure and possible eviction. Kubernetes → Application Telemetry: evictions explain telemetry gaps but do not by themselves explain the pressure. Metrics → Traces: pressure windows guide latency inspection.

## Evidence Safety Rules
Working set predicts OOM risk better than usage-with-cache. Correlation of memory and load is not proof of a leak. Pressure is a precursor, not a completed failure. Empty eviction results are not proof of none.