# Pod Eviction (Node Maintenance / Preemption)

tags: kubernetes, node, scheduling, eviction

## Symptoms

- Pods terminate with reason `Evicted`, often several at once on the same node.
- Node shows `NotReady`, or a spot-instance termination notice fired.
- `kubectl get events --sort-by=.lastTimestamp` shows eviction events clustered in time.

## Diagnosis

1. Check why the node went away:
   `kubectl describe node <node>` — look at conditions and recent events.
2. Distinguish the causes, because the fix differs:
   - Spot/preemptible termination: cloud provider reclaimed the instance (check the termination notice timestamp).
   - Node maintenance / upgrade: cordon + drain sequence in events.
   - Resource pressure eviction: kubelet evicted pods to relieve memory/disk pressure (see the disk-pressure and OOM runbooks).
3. Check whether evicted pods rescheduled: `kubectl get pods -o wide` — pods stuck Pending means the cluster has no capacity for them.
4. Check PodDisruptionBudgets: `kubectl get pdb -A` — evictions blocked by PDBs will show in the drain events.

## Resolution

- For spot terminations: this is normal. The system should reschedule automatically — if it doesn't, you have a capacity or PDB problem, not an eviction problem.
- Set PodDisruptionBudgets on anything that can't tolerate simultaneous eviction: `minAvailable` for stateless, and think hard about stateful ones.
- Use `terminationGracePeriodSeconds` that matches your app's shutdown time — the default 30s kills slow-draining connections.
- Handle SIGTERM in the app: stop accepting new work, finish in-flight requests, then exit. Most "eviction caused errors" are really "app ignored SIGTERM".
- For upgrades: drain one node at a time and watch error rates between drains.

## Prevention

- Chaos-test evictions in staging: delete a node and watch what happens before production does it for you.
- Keep spare capacity: a cluster at 95% utilization can't absorb an eviction.
