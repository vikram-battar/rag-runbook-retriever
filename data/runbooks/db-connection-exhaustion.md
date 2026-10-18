# Database Connection Exhaustion

tags: postgres, database, connections, pool

## Symptoms

- App logs fill with `FATAL: remaining connection slots are reserved`, `too many clients already`, or pool timeout errors.
- New requests fail while the database itself looks healthy (CPU fine, replication fine).
- Connection count metric climbs monotonically and never comes back down.

## Diagnosis

1. Count connections by state and application:
   `SELECT state, application_name, count(*) FROM pg_stat_activity GROUP BY 1, 2;`
2. `idle in transaction` piling up means the app opens transactions and never closes them — the usual suspect.
3. Check `max_connections` on the server vs. what the pool is configured to open: `SHOW max_connections;`
4. Look for connection leaks after deploys — a new version that forgets to close connections will show a step-change at deploy time.
5. Check for long-running queries holding connections: `SELECT pid, now() - query_start AS duration, query FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC LIMIT 10;`

## Resolution

- Immediate relief: kill idle-in-transaction backends older than a threshold:
  `SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'idle in transaction' AND now() - state_change > interval '5 minutes';`
- Put PgBouncer (or RDS Proxy) in transaction-pooling mode between the app and the database. This is the fix that actually holds.
- Fix the app: connections must be closed in a `finally` block / context manager. Audit every code path that opens one.
- Size the pool from the app side: pool size ≈ (2 × CPU cores) + spare is a sane starting point, not "as many as possible".
- Set `statement_timeout` and `idle_in_transaction_session_timeout` so one bad deploy can't wedge the database forever.

## Prevention

- Alert on connection count > 80% of max, and on growth rate, not just the absolute number.
- Every deploy gets a connection-count canary check for 15 minutes post-rollout.
