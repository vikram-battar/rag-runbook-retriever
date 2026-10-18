# Queue Lag (Workers Not Keeping Up)

tags: celery, rabbitmq, workers, queue

## Symptoms

- Queue depth / consumer lag grows monotonically; messages sit unprocessed.
- End-to-end task latency climbs; users see stale results.
- Workers look healthy (running, no restarts) but throughput is flat.

## Diagnosis

1. Check the queue depth trend — growing linearly means consumers are slower than producers, not stuck:
   RabbitMQ: queue depth via management API. Kafka: consumer lag per partition.
2. Check worker concurrency vs. task duration: 4 workers × 30s tasks = 8 tasks/min max. Do the math before assuming a bug.
3. Look for poison messages: one task that always fails and retries can block a whole worker (especially with prefetch=1 and no visibility timeout).
4. Check downstream dependencies: workers waiting on a slow database look like slow workers.
5. Look at retry storms: a failing downstream causes retries that multiply the load — the queue grows because of the retries, not the original traffic.

## Resolution

- Scale workers horizontally first to stop the bleeding — then find the cause.
- Quarantine poison messages: dead-letter queue with a max-retry count, alert on DLQ depth.
- Set task timeouts and visibility timeouts so a stuck task doesn't hold a worker forever.
- If a downstream is slow, add caching or batching at the worker — don't just add workers to wait faster.
- Backpressure: when lag crosses a threshold, shed low-priority tasks or pause producers rather than letting the queue grow unbounded.

## Prevention

- Alert on lag growth rate, not just absolute depth — a deep but stable queue is fine, a growing one is not.
- Autoscale workers on queue depth with sane min/max bounds.
