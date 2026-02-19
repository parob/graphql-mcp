---
title: "Existing GraphQL APIs"
---

# Existing GraphQL APIs

Connect to any existing GraphQL API and expose it as MCP tools — regardless of what language or framework the API is built with. If it speaks GraphQL, graphql-mcp can wrap it.

## Basic Usage

```python
from graphql_mcp import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url="https://countries.trevorblades.com/",
    name="Countries API"
)

app = server.http_app()
```

All queries and mutations from the API are now available as MCP tools.

## Authentication

### Bearer Token

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_your_github_token",
    name="GitHub API"
)
```

### Custom Headers

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    headers={
        "X-API-Key": "your_api_key",
        "X-Custom-Header": "value"
    },
    name="Custom API"
)
```

### Environment Variables

Use environment variables for sensitive data:

```python
import os

server = GraphQLMCP.from_remote_url(
    url=os.getenv("GRAPHQL_URL"),
    bearer_token=os.getenv("GRAPHQL_TOKEN"),
    name=os.getenv("SERVICE_NAME", "Remote API")
)
```

```bash
export GRAPHQL_URL=https://api.example.com/graphql
export GRAPHQL_TOKEN=your_token
python server.py
```

## Popular APIs

### GitHub

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token=os.getenv("GITHUB_TOKEN"),
    name="GitHub"
)
```

Generate a token at [github.com/settings/tokens](https://github.com/settings/tokens).

### Shopify

```python
server = GraphQLMCP.from_remote_url(
    url=f"https://{shop_name}.myshopify.com/admin/api/2024-01/graphql.json",
    bearer_token=os.getenv("SHOPIFY_ACCESS_TOKEN"),
    name="Shopify"
)
```

### Hasura

```python
server = GraphQLMCP.from_remote_url(
    url="https://your-hasura-instance.hasura.app/v1/graphql",
    headers={"x-hasura-admin-secret": os.getenv("HASURA_SECRET")},
    name="Hasura"
)
```

### Contentful

```python
server = GraphQLMCP.from_remote_url(
    url=f"https://graphql.contentful.com/content/v1/spaces/{space_id}",
    bearer_token=os.getenv("CONTENTFUL_TOKEN"),
    name="Contentful"
)
```

## Token Forwarding

By default, `from_remote_url` uses a static `bearer_token` for all requests. To forward the **client's** bearer token from each MCP request instead:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.internal.example.com/graphql",
    forward_bearer_token=True
)
```

> **Security warning:** Client authentication tokens are shared with the remote server. Only enable if you trust the remote server completely. Always use HTTPS.

## Timeout and SSL

### Timeout

The default request timeout is 30 seconds. Adjust for slow APIs:

```python
server = GraphQLMCP.from_remote_url(
    url="https://slow-api.example.com/graphql",
    timeout=60  # seconds
)
```

### SSL Verification

SSL certificate verification is enabled by default. For development with self-signed certificates:

```python
# Development only — do not disable in production
server = GraphQLMCP.from_remote_url(
    url="https://localhost:8443/graphql",
    verify_ssl=False
)
```

## Read-Only Mode

Disable mutation tools for safety:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="token",
    allow_mutations=False
)
```

## Troubleshooting

### Connection Refused

- Verify the URL is correct and the API is accessible from your server
- Check network connectivity and firewall rules

### Authentication Failed

- Verify token format (some APIs need "Bearer " prefix, others don't)
- Check token hasn't expired
- Confirm token has required permissions

### Schema Introspection Failed

GraphQL MCP requires introspection to generate tools. Some APIs disable introspection in production — this is a hard requirement.

### CORS Errors

CORS only applies to browser requests. Server-to-server connections (like GraphQL MCP) are not affected.

See also: [Configuration](/configuration) for auth, mcp_hidden, and middleware, [API Reference](/api-reference) for the full `from_remote_url` parameter reference.
