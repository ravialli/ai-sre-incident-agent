---
title: CPU Saturation and Throttling
category: resources
services:
  - ad
  - currency
  - product-catalog
  - recommendation
technologies:
  - kubernetes
  - mimir
  - loki
severity: medium-high
read_only: true
---

# CPU Saturation and Throttling

## Purpose
Covers CPU-bound conditions in the OpenTelemetry Demo: high CPU utilization, CFS throttling, and the resulting latency/queueing. The demo's `adServiceHighCpu` and `adManualGc` flags can drive CPU load in `ad`. Retrieve when throttling rises or CPU approaches limits. Do not infer CPU saturation from high latency alone — require CPU/throttling evidence.

## Symptoms
- Metrics: high CPU usage vs limit; rising `container_cpu_cfs_throttled_seconds_total` and throttled periods.
- Logs: slow-processing warnings; GC pauses.
- Traces: increased self-time on CPU-bound spans; queueing latency.
- Kubernetes: near the CPU limit; possible liveness-probe timeouts under starvation.

## Signals to Check
### Metrics — CPU utilization, throttling, latency, saturation
Throttling rate: `rate(container_cpu_cfs_throttled_seconds_total{namespace="otel-demo", pod=~"ad.*"}[5m])`.
CPU vs limit: `rate(container_cpu_usage_seconds_total{namespace="otel-demo", pod=~"ad.*"}[5m]) / kube_pod_container_resource_limits{resource="cpu", pod=~"ad.*"}`.
### Logs — GC/slow-processing
`{namespace="otel-demo", service_name="ad"} |~ "gc|slow"`.
### Traces — CPU-bound self-time
`{ resource.service.name = "ad" && duration > 500ms }` and inspect self-time vs child spans.
### Kubernetes — CPU limits, probe events
`kube_pod_container_resource_limits{namespace="otel-demo", resource="cpu"}`.

## Investigation Steps
1. Confirm throttling is occurring (throttled seconds/periods increasing), not just high latency.
2. Compare CPU usage to the limit; a container can throttle below node saturation because of its own limit.
3. Correlate throttling windows with latency rise on the same service.
4. Check whether `adServiceHighCpu`/`adManualGc` is enabled.
5. Distinguish CPU saturation from GC pauses or lock contention via traces/profiles. Read-only.

## Possible Causes
- Container CPU-limit throttling — observed: throttled periods high while the node has spare CPU.
- Node CPU saturation — observed: node-wide high CPU, many pods slow.
- Inefficient/hot code path or GC — observed: high self-time; GC logs.
- Load increase — observed: request rate up with CPU.

## How to Distinguish Causes
- **Limit-throttle vs node-saturation.** Supported for limit by throttling with node CPU spare; for node by high node CPU and many co-located pods slow. Next: compare container throttling to node CPU utilization.
- **CPU-bound vs downstream-wait.** Supported when span self-time (not child spans) dominates; weakened if a downstream child span dominates (then see `grpc-service-latency.md`/`http-service-latency.md`). Next: inspect the trace span breakdown.
- **Organic vs flag-induced.** Supported if the high-CPU flag is enabled. Next: read flagd config.

## Recommended Actions
### Immediate Investigation
Confirm throttling metrics; compare usage to limit and to node; correlate with latency; check flags and profiles.
### Potential Remediation
A human operator may consider raising CPU limits, scaling replicas (HPA), optimizing the hot path, or disabling the fault flag, once confirmed.
### Prevention
Alert on throttling ratio; CPU headroom in capacity planning; HPA on CPU; continuous profiling.

## Escalation / Unknowns
If profiles are unavailable, the exact hot path may be unknown — escalate with throttling evidence. High latency without CPU evidence is not CPU saturation; keep other hypotheses open.

## Correlation Guidance
Metrics → Metrics: throttling and latency rising together supports CPU causation but is not proof. Metrics → Traces: throttling windows guide which slow traces to inspect for self-time. Kubernetes → Application Telemetry: probe timeouts under CPU starvation may cause restarts.

## Evidence Safety Rules
Never infer CPU saturation from latency alone. Correlation of throttling and latency is not causation. A container can throttle while the node is healthy. Bounded traces/profiles are samples.