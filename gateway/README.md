# Authenticated gateway example

Realmwatch expects your reverse proxy to authenticate viewers and then add
`X-Realmwatch-Upstream` with the value stored in `secrets/upstream_secret`.
Never forward a client-supplied value unmodified. Keep the backend secret in
server-side configuration and restrict network access to the backend.

`nginx.conf.example` illustrates a two-stage gateway: HTTPS -> OAuth2 Proxy
(`auth:4180`) -> a private nginx listener -> Realmwatch. Only publish HTTPS;
the private listener on 8080 must never be exposed. The upstream secret must
be set in that private listener. TLS certificates mount at `/tls`.

Replace example hostnames, addresses and `__UPSTREAM_SECRET__` locally. The
example is a template, not a complete deployment. Run OAuth2 Proxy with your
OIDC provider's issuer/client credentials, a generated cookie secret, secure
HTTP-only cookies, allowed viewer groups, PKCE S256 and an upstream pointing
to the private nginx listener. Set the callback to
`https://realmwatch.example.com:8443/oauth2/callback` if using external port8443.

When your gateway is in Docker, `host.docker.internal` needs an explicit Linux
host-gateway mapping, and the host backend must bind to an address reachable
from that gateway. It cannot reach a backend bound only to host loopback.
Choose an explicit private bind address with REALMWATCH_BIND_ADDRESS and a
firewall that permits only your gateway. A host-based reverse proxy can use
the default loopback bind directly.

Generated gateway configurations and credentials are intentionally ignored by
Git. No provider-specific provisioning script is included: identity/group
administration belongs to your existing identity-provider setup.
