# Postmortem: Incident 103 - Redis Cluster Cache Stampede during Flash Sale

- **Date:** 2026-09-28
- **Severity:** P2 (Major)
- **Impacted Services:** `catalog-service`, `redis-cluster`, `product-inventory`
- **Duration:** 19 minutes
- **Root Cause Category:** Cache Stampede / Thundering Herd

## Executive Summary
Simultaneous TTL expiration on hot product keys caused thousands of concurrent application threads to bypass Redis and execute full table scans against the MySQL database, causing CPU saturation and high latency.

## Root Cause
Product inventory keys were set with deterministic 3600s TTLs without jitter. When the flash sale launched, millions of requests requested the identical expired key at the exact second.

## Telemetry Signals
- OpenTelemetry: Spans showing `db.system=redis`, `redis.command=GET` cache miss rate jumping from 2% to 94%.
- Latency spike on downstream SQL read-replica: p99 rose from 12ms to 2400ms.

## Resolution & Remediation
1. Implemented probabilistic early expiration (XFetch algorithm) and added random TTL jitter (±15%).
2. Configured mutex locks (singleflight pattern) in the Go catalog service so only 1 request populates the cache while others await result.
