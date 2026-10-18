# CPU Throttling

tags: kubernetes, cpu, performance, throttling

## Symptoms

- p99 latency climbs but CPU usage looks "fine" (well under the limit).
- `container_cpu_cfs_throttled_seconds_total` increasing for the container.
- App feels slow under load; adding replicas doesn't help proportionally.

## Diagnosis

1. Check throttling directly — `kubectl top` won't show it:
   `rate(container_cpu_cfs_throttled_seconds_total[5m])` per container. Any sustained value above zero means the cgroup is capping you.
2. Compare `container_cpu_usage_seconds_total` against the CPU limit. Throttling happens at the limit, not at high usage.
3. Common trap: CPU limit set equal to a tiny request (e.g. 100m) "to be safe". The container can never burst.
4. Check whether it's the limit or the node: if the node is saturated, you'll see throttling across many pods plus high steal time.

## Resolution

- Raise or remove the CPU limit. Unlike memory, CPU is compressible — exceeding a limit slows you down instead of killing you, so a generous limit is safe.
- Rule of thumb: set CPU requests from measured p50 usage, leave limits unset or 2-4x the request.
- If the app is single-threaded and throttled at 100m, it can never use more than a tenth of a core no matter how idle the node is — size the limit to the thread count.
- For latency-sensitive services, consider `static` CPU manager policy with guaranteed QoS on dedicated nodes.

## Prevention

- Alert on throttling ratio, not just usage: `throttled_seconds / period > 0.1` sustained.
- Review CPU limits quarterly — the value from launch week is probably wrong now.
