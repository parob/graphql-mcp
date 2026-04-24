# Bridge — hosted MCP for any GraphQL API

Bridge is the hosted companion to graphql-mcp. Paste any GraphQL endpoint into your MCP client, attach your own auth headers, and Bridge exposes every query and mutation as an MCP tool that your agent can call. No code, no servers, no keys to sign up for.

It is the fastest way to get a GraphQL API into Claude, Cursor, or any MCP-speaking client — and a zero-effort demo of what graphql-mcp does under the hood.

## One-line setup

```text
https://bridge.graphql-mcp.com/mcp/<url-encoded GraphQL endpoint>
```

For example, to expose the public [Countries API](https://countries.trevorblades.com):

```json
{
  "mcpServers": {
    "countries": {
      "url": "https://bridge.graphql-mcp.com/mcp/https%3A%2F%2Fcountries.trevorblades.com%2Fgraphql"
    }
  }
}
```

Restart your MCP client and every query the Countries API exposes is now a tool.

## Authenticated APIs

Pass your upstream credentials via your MCP client's headers. Bridge forwards `Authorization`, `X-API-Key`, and `Cookie` to the upstream by default — everything else is stripped.

```json
{
  "mcpServers": {
    "github": {
      "url": "https://bridge.graphql-mcp.com/mcp/https%3A%2F%2Fapi.github.com%2Fgraphql",
      "headers": {
        "Authorization": "Bearer ghp_yourtoken"
      }
    }
  }
}
```

Bridge never stores or logs header values. See [Security](/bridge-security) for details.

## When to use Bridge vs. the library

Bridge is the best place to start — try your API in an MCP client in under a minute. Graduate to the [graphql-mcp library](/existing-apis) when you need any of:

- **Private GraphQL endpoints** not reachable from the public internet.
- **Custom tool shaping** with the `@mcp` directive (rename, hide, annotate).
- **Higher request volume** than Bridge's public rate limit.
- **Co-location** with your API for lower latency.
- **Auth schemes** beyond simple header forwarding.

Bridge and the library share the same engine: anything that works on one works on the other. Moving from Bridge to self-hosted graphql-mcp is a few lines of Python.

## Limits

Bridge is free and anonymous. To keep it that way:

- **60 requests per minute per IP**, token bucket.
- **30 second** upstream timeout.
- **5 MB** maximum upstream response.
- Upstreams must be reachable on the public internet (no RFC1918, loopback, or link-local addresses).
- Upstream schema introspection must be enabled.

If you need more, [self-host Bridge](/bridge-self-hosting) — it's open source.

## How it works

1. Your MCP client sends a `tools/list` or `tools/call` to `bridge.graphql-mcp.com/mcp/<encoded-upstream>`.
2. Bridge validates the upstream URL and rate-limits by IP.
3. On the first hit for a given upstream, Bridge introspects the schema once, builds an MCP tool surface, and caches the whole thing in memory (1 hour TTL).
4. Every subsequent request is a cache hit — Bridge just forwards the query to the upstream, passing your auth headers verbatim.

Bridge is built directly on [`GraphQLMCP.from_remote_url()`](/existing-apis). It adds caching, SSRF protection, header allowlisting, and rate limiting on top — nothing more.
