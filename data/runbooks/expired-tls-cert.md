# Expired TLS Certificate

tags: tls, ingress, certificates, cert-manager

## Symptoms

- Browsers show `NET::ERR_CERT_DATE_INVALID`; `curl` fails with `certificate has expired`.
- API clients start failing TLS handshakes at the same time across the board.
- If cert-manager manages it: `kubectl describe certificate <name>` shows `NotAfter` in the past, or the CertificateRequest stuck.

## Diagnosis

1. Check the expiry from outside:
   `echo | openssl s_client -connect example.com:443 -servername example.com 2>/dev/null | openssl x509 -noout -dates`
2. If cert-manager is in play:
   `kubectl get certificate,certificaterequest,order,challenge -A` — find which step is stuck.
3. Common stuck causes: failed ACME HTTP-01 challenge (ingress misrouted), DNS-01 credentials expired, or the issuer's ClusterIssuer account key invalid.
4. Check cert-manager logs: `kubectl logs -n cert-manager deploy/cert-manager | grep <certificate-name>`.

## Resolution

- Renew immediately: `kubectl delete certificaterequest <stuck-request>` to force a re-issue, or `cmctl renew <certificate>`.
- If ACME is failing, fix the underlying challenge path first (DNS record, ingress rule), then re-trigger.
- Verify the new cert is served: re-run the openssl check and confirm `notAfter` moved.
- Set up expiry alerting: alert 30 days and 7 days before `notAfter` on every served certificate. cert-manager exposes `certmanager_certificate_expiration_timestamp_seconds`.
- Keep a runbook entry for the manual renewal path — automation fails the week you need it most.

## Prevention

- Never let certificate renewal be a thing a human remembers to do. Monitor expiry as a metric, not a calendar event.
