# OOMKilled CrashLoop

tags: kubernetes, memory, crashloop, oomkilled

## Symptoms

- Pod restarts repeatedly, `kubectl get pods` shows `CrashLoopBackOff`.
- `kubectl describe pod` shows last state terminated with reason `OOMKilled` and exit code 137.
- Application logs stop mid-request with no error — the kernel killed the process.

## Diagnosis

1. Confirm the kill reason:
   `kubectl describe pod <pod> | grep -A5 "Last State"`
   Look for `Reason: OOMKilled`.
2. Check whether the limit is too low or the app leaks:
   `kubectl top pod <pod>` and compare against `resources.limits.memory`.
3. Look at the memory trend before the kill:
   `kubectl logs <pod> --previous` plus your metrics dashboard for container_memory_working_set_bytes.
4. A steady climb to the limit means a leak. A sudden spike means a traffic or batch-size problem.

## Resolution

- Short term: raise `resources.limits.memory` to stop the crashloop.
- Set `resources.requests.memory` to the steady-state usage so the scheduler places the pod on a node with headroom.
- If it's a JVM app, set `-Xmx` to ~75% of the container limit — the JVM doesn't know about cgroup limits by default on older versions.
- For a real leak: take a heap dump before the kill (`-XX:+HeapDumpOnOutOfMemoryError`) and fix the code. Raising the limit on a leak just delays the page.
- Add an alert on `container_memory_working_set_bytes / container_spec_memory_limit_bytes > 0.9` so you hear about it before the kill.

## Prevention

- Always set memory limits. An OOMKilled pod is a loud, debuggable failure; a node under memory pressure is a mystery.
- Load-test with production-shaped traffic before raising limits blindly.
