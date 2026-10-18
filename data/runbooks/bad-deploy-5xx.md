# Bad Deploy: 5xx Spike

tags: kubernetes, deployment, http, rollout

## Symptoms

- 5xx rate jumps within minutes of a deploy finishing.
- The new ReplicaSet's pods are running but returning 500/502/503.
- Rollback candidate: the previous ReplicaSet is still around.

## Diagnosis

1. Confirm correlation: check deploy time (`kubectl rollout history deployment/<name>`) against the 5xx spike start.
2. Compare old vs new: `kubectl diff` isn't for this — check the image tag and env changes between revisions.
3. Read the new pods' logs first: `kubectl logs -l app=<name> --tail=200` — most bad deploys log their own cause (missing env var, failed migration, bad config).
4. Check readiness probes: pods passing readiness but failing requests means the probe doesn't exercise the broken path.
5. Look for migration issues: did the deploy run a DB migration? Check the migration job's logs separately.

## Resolution

- Roll back first, investigate second: `kubectl rollout undo deployment/<name>`. A 5xx spike is not the time for a forward fix.
- Verify the rollback worked: 5xx rate should drop within a minute or two.
- Then find the cause in staging: missing environment variable, schema migration that wasn't backward compatible, config value in the wrong format.
- Common repeat offenders: migrations that aren't backward compatible with the old code still running during a rolling update; new required env vars not added to the deployment manifest.
- Harden the pipeline: smoke-test the new pods against real endpoints before the rollout completes, not after.

## Prevention

- Require backward-compatible migrations (expand then contract, never both at once).
- Canary or blue-green for anything user-facing; rolling updates hide partial breakage.
