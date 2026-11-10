# Runbook: Kubernetes Pod CrashLoopBackOff & OOMKilled Remediation

## Symptoms & Identification
- Pod status shows `CrashLoopBackOff` or `Error`.
- `kubectl describe pod <pod-name>` shows `Last State: Terminated`, `Reason: OOMKilled`, `Exit Code: 137`.
- OpenTelemetry traces exhibit repeated server span termination and upstream 502/503 errors.

## Immediate Mitigation Steps
1. **Identify the affected deployment**:
   ```bash
   kubectl get pods -n production | grep -E 'CrashLoopBackOff|OOMKilled'
   ```
2. **Inspect resource limits**:
   ```bash
   kubectl describe pod <pod-name> -n production | grep -A 5 Limits
   ```
3. **Temporarily increase memory limits (Emergency Bump)**:
   ```bash
   kubectl set resources deployment/<deployment-name> -n production --limits=memory=2Gi --requests=memory=1Gi
   ```
4. **Capture memory dump if available**:
   ```bash
   kubectl logs <pod-name> -n production --previous --tail=200
   ```
5. **Verify stability**:
   ```bash
   kubectl rollout status deployment/<deployment-name> -n production
   ```
