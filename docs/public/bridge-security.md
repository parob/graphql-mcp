# Bridge — security & privacy

Bridge is a public, anonymous service. These are the guarantees it makes and the protections it enforces.

## What Bridge does and doesn't see

- **Headers you send** are forwarded to the upstream (from a safe allowlist) and otherwise pass through Bridge's process memory for the duration of one request. Bridge does **not** log header values, does **not** persist them, and does **not** share them across requests.
- **GraphQL query bodies and responses** pass through Bridge's process memory and are not logged.
- **Upstream URL, HTTP status, timing, client IP, and a coarse error message** are logged for operational monitoring. These are retained with the deployment's standard log retention.

## Header forwarding allowlist

Bridge forwards this fixed set of headers from your MCP client to the upstream:

- `Authorization`
- `X-API-Key`
- `Cookie`

Hop-by-hop and framing headers (`Host`, `Content-Length`, `Content-Type`, `Connection`, `Transfer-Encoding`, `Upgrade`, `Keep-Alive`, `Proxy-Authorization`, `Proxy-Connection`, `TE`, `Trailer`, `Expect`, `Accept-Encoding`) are **always stripped**, even in self-hosted deployments that set `BRIDGE_FORWARD_HEADERS="*"`.

If your upstream needs a header that isn't on the default list, [self-host Bridge](/bridge-self-hosting) and set `BRIDGE_FORWARD_HEADERS` explicitly.

## SSRF protection

Bridge will refuse to proxy requests whose upstream hostname resolves to:

- loopback (`127.0.0.0/8`, `::1`)
- private (`10.0.0.0/8`, `172.16.0.0/12`, `192.168.0.0/16`, fc00::/7)
- link-local (`169.254.0.0/16`, `fe80::/10`)
- multicast
- reserved / unspecified addresses

DNS resolution happens at request time, so an upstream that *later* starts resolving to a private address is still blocked on the next request.

This protects both Bridge's own infrastructure and the broader internal networks it runs in from being reachable via proxy abuse.

## Rate limiting

Per-IP token bucket: 60 requests / minute by default. Exceeding the limit returns `429 Too Many Requests`.

When traffic comes through a shared NAT, all users behind that NAT share the bucket. Self-hosting removes the shared-tenancy constraint entirely.

## Upstream caps

- **Timeout**: 30 seconds. Upstreams that take longer get a 504 returned to your MCP client.
- **Max URL length**: 2 KB for the upstream URL itself.
- **Max response size**: enforced at the HTTP client layer.

## Transport

Bridge requires HTTPS for connections to `bridge.graphql-mcp.com`. Your upstream can be HTTP or HTTPS, but HTTP upstreams mean your auth headers travel in the clear from Bridge to the upstream — always prefer HTTPS upstreams.

## Reporting abuse or security issues

Email `security@graphql-mcp.com`. Responsible disclosure welcome.

## Self-hosting

If any of the guarantees above aren't strong enough for your use case, Bridge is open source and designed to run as a single container. See [Self-hosting Bridge](/bridge-self-hosting).
