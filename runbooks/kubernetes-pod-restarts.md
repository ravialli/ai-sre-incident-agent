---
title: Kubernetes Pod Restarts
category: kubernetes
services:
  - recommendation
  - cart
  - checkout
  - ad
  - product-catalog
technologies:
  - kubernetes
  - mimir
  - loki
severity: medium-high
read_only: true
---

# Kubernetes Pod Restarts

## Purpose
Covers OpenTelemetry Demo containers restarting repeatedly. Retrieve when `kube_pod_container_status_restarts_total` increases for `otel-demo` pods. A restart is evidence of process-lifecycle disruption; the root cause still requires inspecting the termination reason, logs, events, probes, and resource conditions. A restart is not itself a root cause.

## Symptoms
- Metrics: increasing `kube_pod_container_status_restarts_total`.
- Logs: startup logs repeating; crash stack traces preceding termination.
- Traces: gaps or missing spans during restart windows.
- Kubernetes: `Last State: Terminated` with a reason and exit code; probe-failure events.

## Signals to Check
### Metrics — pod restart counts, availability
`increase(kube_pod_container_status_restarts_total{namespace="otel-demo"}[1h])`; `kube_pod_container_status_last_terminated_reason{namespace="otel-demo"}`.
### Logs — restart messages, crash traces
`{namespace="otel-demo", service_name="recommendation"} |~ "start|panic|fatal"`.
### Traces — missing spans during restart
Compare trace volume for the service before vs during the restart.
### Kubernetes — termination reason, exit code, probes, events
`kubectl describe pod` fields: `Last State`, `Reason`, `Exit Code`; readiness/liveness probe events.

## Investigation Steps
1. Identify the restarting container and its frequency.
2. Read `kube_pod_container_status_last_terminated_reason` to classify: `OOMKilled` (→`kubernetes-oomkill.md`), `Error`/CrashLoop (→`kubernetes-crashloopbackoff.md`), or clean completion.
3. Inspect Kubernetes events for probe failures vs OOM vs image pull.
4. Read logs from the previous container instance for the crash cause.
5. Correlate restart timing with a deployment or config change. Read-only; any change is a human recommendation.

## Possible Causes
- OOMKilled — observed: termination reason `OOMKilled`, exit code 137.
- Application crash — observed: reason `Error`, a non-137 exit, a stack trace.
- Liveness probe failing — observed: probe-failure events restarting a live-but-slow process.
- Node disruption/eviction — observed: node NotReady or under pressure.

## How to Distinguish Causes
- **OOM vs crash.** Supported for OOM by reason `OOMKilled`/exit 137 and memory near the limit; weakened if the reason is `Error` with a code stack trace. Next: read `kube_pod_container_status_last_terminated_reason` and prior-instance logs.
- **Liveness-driven vs genuine crash.** Supported when the process is otherwise healthy but a liveness probe times out (often under CPU pressure); weakened if the process exits on its own. Next: inspect probe config/events and check throttling.
- **Node-level vs pod-level.** Supported if multiple pods on one node restart together and the node shows pressure. Next: `kube_node_status_condition`.

## Recommended Actions
### Immediate Investigation
Classify via the termination reason; read prior-instance logs; inspect events and probes; check node conditions.
### Potential Remediation
A human operator may consider adjusting probes, fixing the crash, raising limits (if OOM), or draining a bad node, once evidence confirms.
### Prevention
Alerts on restart rate; readiness/liveness tuning; resource sizing; graceful-shutdown handling.

## Escalation / Unknowns
If prior-instance logs rolled over, the cause may be unrecoverable from logs alone; escalate with the termination reason. Missing logs reduce confidence and are not proof of a clean restart.

## Correlation Guidance
Kubernetes → Application Telemetry: a restart spike may explain missing traffic/traces, but correlation alone does not establish the restart as the root cause. Metrics → Logs: a restart increase guides which prior-instance logs to read.

## Evidence Safety Rules
A restart is a symptom; do not report it as a cause. Exit code 137 usually but not always means OOM — verify the reason. Empty trace results during a restart mean uncertainty, not zero traffic.