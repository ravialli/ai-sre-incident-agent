---
title: Database Latency
category: database
services:
  - product-catalog
  - accounting
  - cart
technologies:
  - postgresql
  - valkey
  - opentelemetry
  - tempo
  - mimir
  - loki
severity: high
read_only: true
---

# Database Latency

## Purpose
Covers slow data-store operations in the OpenTelemetry Demo: `product-catalog`→PostgreSQL (astronomy-db), `accounting`→PostgreSQL, and `cart`→Valkey cache. Retrieve when DB client operation duration rises or DB spans dominate a trace's critical path. The OpenTelemetry `db.client.operation.duration` metric value should match the database operation span duration,  so metric and trace evidence should agree. A slow DB span in a caller may be a symptom of DB-side or connection-pool issues.

## Symptoms
- Metrics: rising p95 of `db_client_operation_duration_seconds_bucket`; connection-pool waits/timeouts.
- Logs: slow-query lines; pool-exhaustion; connection errors.
- Traces: `db.system.name` spans (`postgresql` / `redis`) dominating the parent duration; `db.query.text`/`db.operation.name` attributes.
- Kubernetes: DB or cache pod resource pressure.

## Signals to Check
### Metrics — DB latency, connection pool, dependency latency
`histogram_quantile(0.95, sum by (le) (rate(db_client_operation_duration_seconds_bucket{namespace="otel-demo", service_name="product-catalog"}[5m])))`; pool metrics `db_client_connection_*` if present.
### Logs — slow query, pool exhaustion
`{namespace="otel-demo", service_name="product-catalog"} |= "query" |= "slow"`.
### Traces — DB spans on the critical path
`{ resource.service.name = "product-catalog" && span.db.system.name = "postgresql" && duration > 200ms } | select(span.db.operation.name)`.
### Kubernetes — DB/cache pod state
Resource usage of the PostgreSQL/Valkey pods.

## Investigation Steps
1. Confirm DB spans (not application code) dominate the slow parent span.
2. Break DB latency down by operation/statement to find the slow query.
3. Determine whether latency is query execution vs waiting for a pooled connection (pool exhaustion looks like DB latency but is a client-side wait).
4. Check the datastore pod's CPU/memory/IO pressure.
5. Correlate with load and with the `productCatalogFailure` flag (error injection for product ID `OLJCESPC7Z`). Read-only.

## Possible Causes
- Slow/blocking query or missing index — observed: one statement dominates.
- Connection-pool exhaustion — observed: pool wait/timeout metrics; latency without high DB CPU.
- Datastore resource saturation — observed: DB pod CPU/IO high.
- Load increase — observed: query rate up.

## How to Distinguish Causes
- **Query vs pool.** Supported for a query by a single statement's execution time dominating; for a pool by rising connection wait/timeout with low DB CPU. Next: compare `db_client_operation_duration_seconds` to pool-wait metrics.
- **Datastore-side vs client-side.** Supported for datastore by DB pod saturation; for client by pool waits while the DB is idle. Next: inspect DB pod resources.
- **Cache (Valkey) vs DB.** For `cart`, a slow Valkey span points to the cache, not PostgreSQL. Next: filter by `span.db.system.name`.

## Recommended Actions
### Immediate Investigation
Confirm DB spans dominate; break down by statement; separate query time from pool wait; check datastore resources.
### Potential Remediation
A human operator may consider adding indexes, tuning queries, resizing the pool, scaling the datastore, or disabling the fault flag, once confirmed.
### Prevention
Query-level dashboards; pool-utilization alerts; DB capacity planning; slow-query logging; a caching strategy.

## Escalation / Unknowns
If DB-internal metrics (beyond client spans) are unavailable, attribution of query vs server is limited — escalate to the DB owner. Missing DB telemetry reduces confidence.

## Correlation Guidance
Traces → Metrics: a dominating DB span names the operation to query in `db_client_operation_duration_seconds`. Metrics → Logs: slow-query windows guide log inspection. Logs → Traces: a slow-query log with a `trace_id` links to the trace.

## Evidence Safety Rules
A slow DB span in a caller may reflect a pool wait, not query execution — verify. Bucket ceilings approximate latency. Correlation of load and DB latency is not proof of a query bug. Bounded log/trace results are samples.