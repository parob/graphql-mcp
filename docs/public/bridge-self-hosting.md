# Self-hosting Bridge

Bridge is open source: [`parob/graphql-mcp-bridge`](https://github.com/parob/graphql-mcp-bridge). Self-host when you need private upstreams, higher rate limits, custom header allowlists, or co-location with your API.

## Quick start

```bash
git clone https://github.com/parob/graphql-mcp-bridge
cd graphql-mcp-bridge
uv sync
uv run uvicorn bridge.app:app --reload
```

Then point any MCP client at `http://localhost:8000/mcp/<url-encoded GraphQL URL>`.

## Configuration

All settings read from env vars at startup:

| Variable                             | Default                            | Description                                              |
| ------------------------------------ | ---------------------------------- | -------------------------------------------------------- |
| `BRIDGE_CACHE_MAXSIZE`               | `1000`                             | Max cached upstreams                                     |
| `BRIDGE_CACHE_TTL_SECONDS`           | `3600`                             | TTL per cached introspection result                      |
| `BRIDGE_UPSTREAM_TIMEOUT_SECONDS`    | `30`                               | Request timeout to upstream                              |
| `BRIDGE_MAX_UPSTREAM_URL_LENGTH`     | `2048`                             | Reject upstream URLs longer than this                    |
| `BRIDGE_RATE_LIMIT`                  | `60/minute`                        | Per-IP token bucket (`<count>/<second\|minute\|hour>`) |
| `BRIDGE_FORWARD_HEADERS`             | `authorization,x-api-key,cookie`   | Allowlisted headers, or `*` for all safe headers         |
| `BRIDGE_ALLOW_INTERNAL_HOSTS`        | `false`                            | Allow upstreams on loopback / RFC1918 (trusted networks) |
| `BRIDGE_ADMIN_SECRET`                | *(unset)*                          | Enables `POST /admin/invalidate` if set                  |
| `BRIDGE_USER_AGENT`                  | `graphql-mcp-bridge/0.1 (+…)`      | User-Agent sent to upstreams                             |

## Deploy to Cloud Run

Bridge is stateless, scale-to-zero friendly, single container.

```bash
gcloud run deploy graphql-mcp-bridge \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --min-instances 0 \
  --max-instances 1 \
  --concurrency 80
```

One instance with `concurrency=80` handles up to 80 in-flight MCP requests at once — Bridge is fully async end-to-end, so the ceiling is your upstream's latency, not Bridge itself.

## Internal / private upstreams

Set `BRIDGE_ALLOW_INTERNAL_HOSTS=true` when Bridge is deployed inside a VPC that reaches private GraphQL endpoints. Only do this on trusted networks — it disables SSRF protection.

## Custom header allowlist

Most self-hosted deployments need to forward API-specific headers. Override the default with a comma-separated list:

```bash
export BRIDGE_FORWARD_HEADERS="authorization,x-api-key,x-tenant-id,x-trace-id"
```

Set to `*` to forward everything except hop-by-hop headers (still stripped).

## When Bridge isn't enough

Bridge is deliberately thin — it's a proxy in front of [`GraphQLMCP.from_remote_url()`](/existing-apis). If you need deeper control:

- **Shape the tool surface** with the `@mcp` directive (rename / hide / annotate): use the [graphql-mcp library directly](/configuration#mcp-directive).
- **Wrap an in-process schema** to skip the network hop entirely: see [Python Libraries](/python-libraries).
- **Custom auth** beyond header forwarding (JWT introspection, OAuth refresh, etc.): build a thin service on graphql-mcp.

Bridge exists to get you started in a minute. When you're ready, graduate to the library.
