---
title: "Remote GraphQL"
weight: 3
---

# Remote GraphQL APIs

GraphQL MCP can connect to existing GraphQL APIs and expose them as MCP tools, making it easy to integrate third-party services or existing GraphQL backends.

## Basic Usage

Connect to any GraphQL endpoint:

```python
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url="https://countries.trevorblades.com/",
    name="Countries API"
)

app = server.http_app()
```

That's it! All queries and mutations from the remote API are now available as MCP tools.

## With Authentication

Many APIs require authentication. GraphQL MCP supports bearer tokens:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_your_github_token",
    name="GitHub API"
)
```

## Custom Headers

Add any custom headers your API requires:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="your_token",
    headers={
        "X-API-Key": "your_api_key",
        "X-Custom-Header": "value"
    },
    name="Custom API"
)
```

## Environment Variables

Use environment variables for sensitive data:

```python
import os

server = GraphQLMCP.from_remote_url(
    url=os.getenv("GRAPHQL_URL"),
    bearer_token=os.getenv("GRAPHQL_TOKEN"),
    name=os.getenv("SERVICE_NAME", "Remote API")
)
```

Run with:

```bash
export GRAPHQL_URL=https://api.example.com/graphql
export GRAPHQL_TOKEN=your_token
python server.py
```

## Popular APIs

### GitHub API

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token=os.getenv("GITHUB_TOKEN"),
    name="GitHub"
)
```

Generate a token at: https://github.com/settings/tokens

### Shopify API

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
    headers={
        "x-hasura-admin-secret": os.getenv("HASURA_SECRET")
    },
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

## Configuration Options

### Read-Only Mode

Disable mutation tools for safety:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="token",
    name="Read-Only API"
)

# Disable mutations
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="token",
    name="Read-Only API",
    allow_mutations=False  # This option would need to be added to from_remote_url
)
```

### With Inspector

Enable the MCP Inspector for testing:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="token",
    graphql_http=True,  # Enable GraphQL endpoint and inspector
    name="Example API"
)
```

## Testing Remote Connections

Use the MCP Inspector to test your remote connection:

```python
import uvicorn
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url="https://countries.trevorblades.com/",
    graphql_http=True,  # Enable inspector
    name="Countries"
)

app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="localhost", port=8000)
```

Visit `http://localhost:8000/graphql` to:
- Browse available tools
- Test queries with parameters
- Verify authentication
- Inspect response schemas

## Error Handling

GraphQL MCP automatically handles common errors:

### Network Errors

```python
try:
    server = GraphQLMCP.from_remote_url(
        url="https://api.example.com/graphql",
        bearer_token="token"
    )
except Exception as e:
    print(f"Failed to connect: {e}")
```

### Authentication Errors

If your token is invalid, you'll see authentication errors when testing tools.

### Rate Limiting

Some APIs have rate limits. GraphQL MCP passes through rate limit errors from the remote API.

## Best Practices

### 1. Use Environment Variables

Never hardcode tokens:

```python
# ❌ Bad
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="hardcoded_token_123"
)

# ✅ Good
server = GraphQLMCP.from_remote_url(
    url=os.getenv("GRAPHQL_URL"),
    bearer_token=os.getenv("GRAPHQL_TOKEN")
)
```

### 2. Test with Inspector First

Always test remote connections with the inspector before production:

```python
# Development
server = GraphQLMCP.from_remote_url(
    url=url,
    bearer_token=token,
    graphql_http=True  # Enable for testing
)

# Production
server = GraphQLMCP.from_remote_url(
    url=url,
    bearer_token=token,
    graphql_http=False  # Disable in production
)
```

### 3. Handle Token Refresh

For APIs with expiring tokens, implement token refresh:

```python
def get_current_token():
    # Your token refresh logic
    return refresh_token()

server = GraphQLMCP.from_remote_url(
    url=url,
    bearer_token=get_current_token()
)
```

### 4. Add Timeouts

For production use, consider adding request timeouts in your HTTP client configuration.

## Combining Local and Remote

You can proxy some operations locally while forwarding others:

```python
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

# Local API with custom logic
class LocalAPI:
    @field
    def local_operation(self) -> str:
        return "Handled locally"

# Create combined server
local_api = GraphQLAPI(root_type=LocalAPI)

# For remote-only, use from_remote_url
# For local+custom, you'd extend the schema
```

## Troubleshooting

### Connection Refused

- Verify the URL is correct
- Check network connectivity
- Ensure the API is accessible from your server

### Authentication Failed

- Verify token format (some APIs need "Bearer " prefix, others don't)
- Check token hasn't expired
- Confirm token has required permissions

### Schema Introspection Failed

Some APIs disable introspection in production. GraphQL MCP requires introspection to generate tools.

### CORS Errors

CORS only applies to browser requests. Server-to-server connections (like GraphQL MCP) don't have CORS restrictions.

## Next Steps

- **[Configuration](configuration/)** - Learn about all configuration options
- **[MCP Inspector](mcp-inspector/)** - Test your remote connections
- **[Examples](examples/)** - See complete examples
