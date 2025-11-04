---
title: "Configuration"
weight: 2
---

# Configuration

GraphQL MCP provides flexible configuration options for customizing your MCP server behavior.

## Server Creation

### From graphql-api

The recommended way to create an MCP server:

```python
from graphql_api import GraphQLAPI
from graphql_mcp.server import GraphQLMCP

api = GraphQLAPI(root_type=MyAPI)
server = GraphQLMCP.from_api(
    api,
    name="My API",
    graphql_http=True,
    allow_mutations=True,
    auth=None
)
```

### From Remote URL

Connect to an existing GraphQL endpoint:

```python
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="optional_auth_token",
    name="Remote API"
)
```

### From Schema

Use any `graphql-core` schema directly:

```python
from graphql import GraphQLSchema
from graphql_mcp.server import GraphQLMCP

# Your schema from any library (Strawberry, Ariadne, etc.)
schema = GraphQLSchema(...)

server = GraphQLMCP(
    schema=schema,
    name="My Schema"
)
```

## Configuration Options

### GraphQLMCP Parameters

#### schema
**Type:** `GraphQLSchema`
**Required:** Yes (when not using `from_api` or `from_remote_url`)

The GraphQL schema to generate MCP tools from.

```python
server = GraphQLMCP(schema=my_schema)
```

#### name
**Type:** `str`
**Default:** `"GraphQL MCP Server"`

The display name for your MCP server.

```python
server = GraphQLMCP(schema=schema, name="Books API")
```

#### graphql_http
**Type:** `bool`
**Default:** `False`

Whether to enable the GraphQL HTTP endpoint alongside MCP.

```python
server = GraphQLMCP.from_api(api, graphql_http=True)
```

When enabled:
- GraphQL queries can be sent to `/graphql`
- GraphiQL interface is available in the browser
- MCP Inspector is automatically injected

#### allow_mutations
**Type:** `bool`
**Default:** `True`

Whether to generate MCP tools for GraphQL mutations.

```python
# Read-only server
server = GraphQLMCP.from_api(api, allow_mutations=False)
```

#### auth
**Type:** `Optional[JWTVerifier]`
**Default:** `None`

Authentication configuration for protected endpoints.

```python
from graphql_mcp.auth import JWTVerifier

jwt_verifier = JWTVerifier(
    jwks_uri="https://auth.example.com/.well-known/jwks.json",
    issuer="https://auth.example.com/",
    audience="my-api"
)

server = GraphQLMCP.from_api(api, auth=jwt_verifier)
```

## HTTP Application Configuration

The `http_app()` method configures the HTTP transport:

```python
app = server.http_app(
    transport="streamable-http",
    stateless_http=True,
    path="/mcp"
)
```

### Parameters

#### transport
**Type:** `str`
**Default:** `"streamable-http"`
**Options:** `"http"`, `"sse"`, `"streamable-http"`

The MCP transport protocol to use:

- `http` - Simple HTTP request/response
- `sse` - Server-Sent Events for streaming
- `streamable-http` - HTTP with streaming support (recommended)

```python
# Use SSE transport
app = server.http_app(transport="sse")
```

#### stateless_http
**Type:** `bool`
**Default:** `False`

Whether to disable session state management.

```python
# Stateless mode (recommended for serverless)
app = server.http_app(stateless_http=True)
```

Set to `True` for:
- Serverless deployments
- Load-balanced environments
- Simple request/response patterns

#### path
**Type:** `str`
**Default:** `"/mcp"`

The URL path for MCP endpoints.

```python
# Custom path
app = server.http_app(path="/api/mcp")
```

## Remote GraphQL Configuration

When connecting to remote GraphQL APIs:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_your_token_here",
    name="GitHub API",
    headers={
        "X-Custom-Header": "value"
    }
)
```

### Parameters

#### url
**Type:** `str`
**Required:** Yes

The GraphQL endpoint URL.

#### bearer_token
**Type:** `Optional[str]`
**Default:** `None`

Bearer token for authentication.

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="your_token"
)
```

#### headers
**Type:** `Optional[dict]`
**Default:** `None`

Additional HTTP headers to send with requests.

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    headers={
        "X-API-Key": "your_key",
        "X-Custom-Header": "value"
    }
)
```

## Environment Variables

You can use environment variables for configuration:

```python
import os
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url=os.getenv("GRAPHQL_URL"),
    bearer_token=os.getenv("GRAPHQL_TOKEN"),
    name=os.getenv("SERVICE_NAME", "GraphQL API")
)
```

Then run with:

```bash
GRAPHQL_URL=https://api.example.com/graphql \
GRAPHQL_TOKEN=your_token \
SERVICE_NAME="My API" \
python server.py
```

## Production Configuration

For production deployments:

```python
import uvicorn
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_api(
    api,
    name="Production API",
    graphql_http=False,  # Disable GraphiQL in production
    allow_mutations=True,
    auth=jwt_verifier  # Always use authentication
)

app = server.http_app(
    transport="streamable-http",
    stateless_http=True  # Better for load balancing
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        workers=4,  # Multiple workers
        access_log=True,
        log_level="info"
    )
```

## Next Steps

- **[Learn about remote GraphQL](remote-graphql/)** - Connect to existing APIs
- **[Explore the MCP Inspector](mcp-inspector/)** - Test your configuration
- **[Check out examples](examples/)** - See configuration in action
