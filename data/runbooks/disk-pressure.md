# Disk Pressure on Node

tags: kubernetes, node, disk, eviction

## Symptoms

- Node shows `DiskPressure` condition: `kubectl describe node <node> | grep -A3 Conditions`.
- Pods get evicted with reason `Evicted` and message about disk pressure.
- `kubelet` logs mention `imagefs` or `nodefs` crossing eviction thresholds.

## Diagnosis

1. Check what's full — images or the writable layer:
   `df -h` on the node; `du -sh /var/lib/docker/*` (or containerd's `/var/lib/containerd`).
2. Common culprits: unpruned images (`crictl images` lists gigabytes of old tags), runaway container logs (json-file driver with no rotation), or an app writing to the container filesystem instead of a volume.
3. Check log sizes: `du -sh /var/log/pods/*`.
4. Check ephemeral storage usage per pod: `kubectl top pod` won't show it — use the metrics for `container_fs_usage_bytes`.

## Resolution

- Immediate: `crictl rmi --prune` to drop unused images. Cordon the node if evictions are cascading: `kubectl cordon <node>`.
- Fix log rotation: set `containerLogMaxSize` and `containerLogMaxFiles` in the kubelet config.
- If an app writes to the container filesystem, give it an `emptyDir` with a `sizeLimit` so one pod can't fill the node.
- Set `resources.requests/limits` for `ephemeral-storage` on chatty workloads.
- Long term: alert on `node_filesystem_avail_bytes / node_filesystem_size_bytes < 0.15` per mountpoint.

## Prevention

- Image garbage collection thresholds in kubelet config (`imageGCHighThresholdPercent`).
- Never treat the container filesystem as scratch space without a size limit.
