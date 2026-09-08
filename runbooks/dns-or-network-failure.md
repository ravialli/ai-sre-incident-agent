---
title: DNS or Network Failure
category: networking
services:
  - frontend
  - checkout
  - cart
  - product-catalog
  - payment
technologies:
  - kubernetes
  - coredns
  - envoy
  - opentelemetry
  - tempo
  - loki
severity: high
read_only: true
---

# DNS or Network Failure

## Purpose
Covers connectivity problems in the OpenTelemetry Demo: DNS resolution failure, TCP connection failure/refused/reset, connection timeout, service-discovery issues, and TLS failures — as distinct from application-layer timeouts and downstream application latency. Retrieve when connection errors appear. Do not label every timeout a network problem.

## Symptoms
- Metrics: gRPC UNAVAILABLE (14) spikes; CoreDNS SERVFAIL/NXDOMAIN rate; connection-error counters.
- Logs: "no such host"/"name resolution", "connection refused", "connection reset by peer", "i/o timeout", TLS handshake errors.
- Traces: caller span errors with no downstream child span; very short-duration connection errors.
- Kubernetes: CoreDNS pod health; NetworkPolicy; endpoints.

## Signals to Check
### Metrics — DNS responses, connection errors, RPC status
CoreDNS errors: `sum(rate(coredns_dns_responses_total{rcode=~"SERVFAIL|NXDOMAIN"}[5m]))`.
DNS latency: `histogram_quantile(0.99, rate(coredns_dns_request_duration_seconds_bucket[5m]))`. 
Caller UNAVAILABLE rate. (CoreDNS exposes these on the fixed metrics path `/metrics`, default `:9153`.) 
### Logs — resolution/connection/TLS errors
`{namespace="otel-demo", service_name="checkout"} |~ "no such host|connection refused|reset|tls"`.
### Traces — errors with no child span
Caller error spans lacking the expected downstream child.
### Kubernetes — CoreDNS, endpoints, NetworkPolicy
CoreDNS (`kube-system`) pod readiness; Service endpoints; NetworkPolicy presence.

## Investigation Steps
1. Classify the error string: DNS (no such host/SERVFAIL) vs TCP (refused/reset/timeout) vs TLS (handshake).
2. For DNS, check CoreDNS response codes and latency; a cluster-wide SERVFAIL/NXDOMAIN spike affects many services.
3. For TCP refused, check whether the callee has ready endpoints (refused often means nothing is listening → `service-unavailable.md`).
4. For reset/timeout with a healthy callee, suspect the network path or a NetworkPolicy.
5. Confirm the callee's own metrics/logs are healthy to separate network from application fault. Read-only.

## Possible Causes
- DNS resolution failure — observed: "no such host"/SERVFAIL; CoreDNS errors.
- TCP connection refused — observed: refused; callee endpoints empty.
- Connection reset/timeout — observed: reset/i-o timeout with the callee healthy.
- TLS failure — observed: handshake errors.
- Application timeout misclassified — observed: the downstream is simply slow, not unreachable.

## How to Distinguish Causes
- **DNS vs TCP.** Supported for DNS by resolution errors and CoreDNS SERVFAIL/NXDOMAIN; for TCP by refused/reset with successful name resolution. Next: query `coredns_dns_responses_total` by `rcode`.
- **Network vs application.** Supported for network when the callee shows healthy metrics/logs but callers cannot connect; weakened if the callee logs its own errors (then it is an application/downstream issue). Next: inspect callee-side telemetry.
- **Refused vs reset.** Refused implies no listener (availability); reset/timeout implies mid-path disruption or policy. Next: check endpoints and NetworkPolicy.

## Recommended Actions
### Immediate Investigation
Classify the error; check CoreDNS; verify callee endpoints/health; distinguish network from application fault.
### Potential Remediation
A human operator may consider scaling/fixing CoreDNS, correcting NetworkPolicy/Service config, or addressing the callee, once confirmed.
### Prevention
CoreDNS alerts (SERVFAIL rate, latency, replica count); DNS caching / ndots tuning; NetworkPolicy tests; connection-error dashboards; retries with backoff for UNAVAILABLE.

## Escalation / Unknowns
If per-hop network telemetry is missing, exact path attribution is limited — escalate to platform/networking. A timeout is not proof of a network fault; keep application-latency hypotheses open.

## Correlation Guidance
Metrics → Logs: a CoreDNS SERVFAIL spike guides which service logs to read for resolution errors. Traces → Kubernetes: a caller error with no child span points to endpoints/network to verify. Logs → Metrics: connection-refused logs corroborate empty endpoints.

## Evidence Safety Rules
Not every timeout is a network problem — verify callee health first. Refused, reset, and timeout are distinct signals. Correlation of DNS errors and app errors is not proof for a specific service. Empty results are uncertainty, not zero.