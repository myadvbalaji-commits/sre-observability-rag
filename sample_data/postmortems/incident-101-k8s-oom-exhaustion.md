# Postmortem: Incident 101 - Kubernetes Pod OOMKilled in Checkout Service

- **Date:** 2026-08-14
- **Severity:** P1 (Critical)
- **Impacted Services:** `checkout-service`, `payment-gateway`, `frontend-proxy`
- **Duration:** 38 minutes
- **Root Cause Category:** Resource Limits / Memory Leak

## Executive Summary
At 14:22 UTC, the checkout-service pods began crash-looping with exit code 137 (SIGKILL issued by Linux OOM killer). Elevated HTTP 502 Bad Gateway responses were observed across the payment funnel, impacting ~14,200 active checkouts.

## Root Cause
A recent release (v2.14.0) introduced an unconstrained in-memory batch caching mechanism for currency conversion rates. Under peak traffic of 4,200 requests/sec, the memory footprint exceeded the 512Mi container limit within 4 minutes, causing the Kubernetes kernel cgroup OOM killer to terminate pods.

## Trigger & Telemetry Signals
- OpenTelemetry Trace: `span.kind=SERVER`, `http.status_code=502`, span error on `checkout-service.processOrder`
- Kubernetes Event: `Reason: OOMKilled`, `ExitCode: 137`
- Metrics: `container_memory_working_set_bytes` exceeded `container_spec_memory_limit_bytes`

## Resolution & Remediation
1. Scaled pod memory limits from 512Mi to 2Gi via `kubectl patch deployment checkout-service -p '{"spec":{"template":{"spec":{"containers":[{"name":"checkout","resources":{"limits":{"memory":"2Gi"}}}]}}}}'`.
2. Rolled back v2.14.0 to v2.13.9.
3. Added LRU cache eviction policy with max 10,000 items.

## Action Items
- [ ] Enforce automated memory regression tests in staging load-testing pipeline.
- [ ] Implement Horizontal Pod Autoscaler (HPA) targeting memory utilization at 75%.
- [ ] Configure Alertmanager alert for `ContainerMemoryUsageNearLimit` (>85% for 2m).
