# DNS Failure in Cluster

tags: kubernetes, dns, networking, coredns

## Symptoms

- Pods can't resolve service names: `nslookup myservice` times out inside a pod, but IPs work.
- Intermittent `EAI_AGAIN` / `getaddrinfo` errors in app logs.
- External names fail while cluster.local names work, or vice versa.

## Diagnosis

1. Test from a debug pod:
   `kubectl run -it --rm debug --image=busybox --restart=Never -- nslookup kubernetes.default`
2. Check CoreDNS health: `kubectl get pods -n kube-system -l k8s-app=kube-dns` — are they running and ready?
3. Look at CoreDNS logs for forward failures: `kubectl logs -n kube-system -l k8s-app=kube-dns | grep -i "no healthy"`.
4. Check `ndots`: pods with `ndots:5` (the default) send up to 5 queries per lookup; a typo'd name multiplies DNS traffic and can look like an outage under load.
5. Verify the pod's resolv.conf: `kubectl exec <pod> -- cat /etc/resolv.conf` — wrong search domains break resolution silently.
6. If external names fail: check the upstream nameserver CoreDNS forwards to and whether egress allows UDP/TCP 53.

## Resolution

- Restart stuck CoreDNS pods: `kubectl rollout restart deployment coredns -n kube-system`.
- For ndots storms: set `ndots:2` in pod dnsConfig for chatty services, or use fully-qualified names (`myservice.myns.svc.cluster.local.` with trailing dot).
- Fix the upstream: if the forwarder is down, point CoreDNS at a working resolver.
- Scale CoreDNS if it's CPU-throttled under query load — check its resource limits.

## Prevention

- Monitor CoreDNS latency (`coredns_dns_request_duration_seconds`) and forward error rate.
- Add a synthetic DNS probe pod that resolves a known name every minute and alerts on failure.
