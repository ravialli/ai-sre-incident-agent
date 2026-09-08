---
title: Kubernetes CrashLoopBackOff
category: kubernetes
services:
  - cart
  - checkout
  - recommendation
  - ad
  - payment
technologies:
  - kubernetes
  - loki
  - mimir
severity: high
read_only: true
---

# Kubernetes CrashLoopBackOff

## Purpose
Covers OpenTelemetry Demo containers stuck in CrashLoopBackOff: repeated restarts with a non-zero exit, application startup failures, or probe failures during startup. Retrieve when a pod shows `Waiting: CrashLoopBackOff`. Distinguish carefully from OOMKilled and from steady-state pod restarts.

## Symptoms
- Metrics: rapidly increasing `kube_pod_container_status_restarts_total`; pod not `Ready`.
- Logs: startup errors, missing config/env, dependency-unreachable at boot, panics immediately after start.
- Traces: little or no telemetry from the service (it never becomes ready).
- Kubernetes: `State: Waiting, Reason: CrashLoopBackOff`; `Last State: Terminated` with a non-zero exit; escalating backoff delay.

## Signals to Check
### Metrics — restart counts, readiness, availability
`kube_pod_status_phase{namespace="otel-demo"}`; `kube_deployment_status_replicas_unavailable{namespace="otel-demo"}`; restart-counter rate.
### Logs — startup failure, config errors, dependency errors
`{namespace="otel-demo", service_name="cart"} | json | level="error"` focused on boot lines.
### Traces — absence of spans (service never ready)
Confirm the service emits no new spans while looping.
### Kubernetes — waiting reason, exit code, events, probes
`kubectl describe pod`: CrashLoopBackOff, exit code, readiness/liveness events, image, env, mounts.

## Investigation Steps
1. Confirm the waiting reason is CrashLoopBackOff and read the exit code.
2. Read logs from the previous terminated instance — CrashLoop causes are almost always in the earliest startup lines.
3. Check for a missing/incorrect ConfigMap/Secret/env, or a boot dependency the app needs (e.g. `cart`→Valkey, `checkout`→required env).
4. Distinguish exit 137 (startup OOM → `kubernetes-oomkill.md`) from application exits.
5. Check whether a readiness/liveness probe is killing the container before startup completes. Read-only.

## Possible Causes
- Startup misconfiguration — observed: log shows missing env/config; strong.
- Failed boot dependency — observed: "cannot connect" to Valkey/DB/flagd at start.
- Application bug/panic on start — observed: a stack trace immediately after boot.
- Aggressive probe — observed: liveness kills a slow-starting container.
- Startup OOM — observed: exit 137 at boot.

## How to Distinguish Causes
- **Config vs dependency.** Supported for config by explicit "missing/invalid" messages; for dependency by connection errors to Valkey/PostgreSQL/flagd. Next: read the first ~50 log lines of the prior instance.
- **Probe-induced vs genuine crash.** Supported when logs show the process was still initializing when killed and no error precedes termination; weakened if the app logs a fatal error first. Next: inspect liveness `initialDelaySeconds`/`failureThreshold` and events.
- **Startup OOM vs code crash.** Exit 137 plus reason `OOMKilled` supports OOM; a code stack trace supports a bug. Next: `kube_pod_container_status_last_terminated_reason`.

## Recommended Actions
### Immediate Investigation
Read prior-instance startup logs; verify config/secrets/env; check boot dependencies; inspect probe timing.
### Potential Remediation
A human operator may consider fixing config, restoring the dependency, correcting the image, or relaxing startup probes, once confirmed.
### Prevention
Startup/readiness probe tuning with an adequate initial delay; config validation in CI; dependency-ready checks; alert on CrashLoopBackOff.

## Escalation / Unknowns
If the container exits before writing logs, the cause may need image/entrypoint review; escalate to the service owner. Absence of spans/logs is uncertainty, not proof the service is fine.

## Correlation Guidance
Kubernetes → Application Telemetry: CrashLoop explains the absence of the service's spans; the absence does not by itself explain the crash. Metrics → Logs: the restart rate points to which prior-instance logs to read.

## Evidence Safety Rules
CrashLoopBackOff is a state, not a root cause. Exit 137 is not always OOM — verify the reason. Empty telemetry from a looping pod means uncertainty. Tie remediation to the specific startup evidence.