# Review Endpoint Network Access

This deployment note documents trusted-network controls required for review endpoints in v1.

## Scope

- `GET /reviews/latest`
- `GET /reviews`
- `GET /reviews/{id}`
- `POST /admin/reviews/replay`

## v1 Access Model

Application-layer authentication is intentionally not enabled for these endpoints in v1.
Access MUST be restricted at network and proxy layers.

## Required Controls

1. Expose backend service only on private interfaces where possible.
2. Restrict inbound access to trusted CIDR ranges via firewall/security group.
3. Add explicit allowlist rules in nginx for review routes.
4. Deny all non-allowlisted access with `403`.
5. Log denied attempts without leaking secrets.

## Example Nginx Pattern

```nginx
location ~ ^/(reviews|admin/reviews/replay) {
    allow 10.0.0.0/8;
    allow 192.168.0.0/16;
    deny all;

    proxy_pass http://127.0.0.1:8080;
}
```

## Verification

- Confirm access succeeds from allowlisted hosts.
- Confirm `403` from non-allowlisted hosts.
- Re-run this verification after any nginx or network policy changes.
