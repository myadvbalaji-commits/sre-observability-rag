# Postmortem: Incident 102 - PostgreSQL Connection Pool Saturation & Deadlocks

- **Date:** 2026-09-02
- **Severity:** P1 (Critical)
- **Impacted Services:** `user-auth-service`, `billing-api`, `postgres-primary`
- **Duration:** 24 minutes
- **Root Cause Category:** Database Connection Starvation

## Executive Summary
At 09:15 UTC, the billing service experienced connection timeouts reaching `pg_bouncer` and primary PostgreSQL clusters. Authentication and checkout endpoints degraded with HTTP 504 Gateway Timeouts.

## Root Cause
An un-indexed analytics query running concurrently with an uncommitted transaction held an `ExclusiveLock` on the `user_ledgers` table. This backed up all subsequent write transactions, exhausting the 200 maximum client connection limit on PgBouncer.

## Telemetry Signals
- OpenTelemetry Spans: `db.system=postgresql`, `db.statement="SELECT ... FOR UPDATE"`, latency p99 > 30,000ms
- Metrics: `pg_stat_activity` state = `idle in transaction`, waiting for locks
- Error Log: `FATAL: remaining connection slots are reserved for non-replication superuser connections`

## Resolution & Remediation
1. Terminated blocking backend processes via `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND query_start < NOW() - INTERVAL '5 minutes';`.
2. Reduced `statement_timeout` to 5000ms in `postgresql.conf`.
3. Added connection pooling queue limit and rejected slow analytical transactions on primary writer.
