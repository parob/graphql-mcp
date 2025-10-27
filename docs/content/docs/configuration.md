---
title: Configuration
weight: 4
---

# Configuration

Learn how to configure GraphQL MCP to suit your needs.

## Server Configuration

### Basic Options

```python
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_api(
    api,
    name="My API",                # Display name for the MCP server
    graphql_http=True,            # Enable GraphQL HTTP endpoint
    allow_mutations=True,         # Allow mutation tools
)
```

### Transport Options

GraphQL MCP supports multiple transport protocols:

```python
# Streamable HTTP (recommended)
app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)

# Standard HTTP
app = server.http_app(
    transport="http",
    stateless_http=True
)

# Server-Sent Events (SSE)
app = server.http_app(
    transport="sse",
    stateless_http=False  # SSE requires stateful connections
)
```

### Stateful vs Stateless

Choose between stateful and stateless modes:

```python
# Stateless (recommended for most use cases)
app = server.http_app(stateless_http=True)

# Stateful (maintains client state between requests)
app = server.http_app(stateless_http=False)
```

## HTTP Server Configuration

### Port and Host

```python
import uvicorn

uvicorn.run(
    app,
    host="0.0.0.0",  # Listen on all interfaces
    port=8002,        # Custom port
)
```

### Production Settings

For production deployments:

```python
uvicorn.run(
    app,
    host="0.0.0.0",
    port=8002,
    workers=4,                    # Multiple workers
    log_level="info",             # Logging level
    access_log=True,              # Enable access logs
    proxy_headers=True,           # Trust proxy headers
    forwarded_allow_ips="*",      # Allow forwarded IPs
)
```

## CORS Configuration

Enable CORS for browser-based clients:

```python
from starlette.middleware.cors import CORSMiddleware

app = server.http_app()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## GraphQL Endpoint

### Custom Endpoint Path

By default, the GraphQL endpoint is at `/graphql`. To customize:

```python
# This is handled by the underlying ASGI app
# The endpoint path is determined by the server configuration
```

### GraphiQL Interface

When `graphql_http=True`, the GraphiQL interface is automatically available. The MCP Inspector is injected into this interface.

## Tool Configuration

### Filtering Queries and Mutations

Control which GraphQL operations are exposed as tools:

```python
# Only expose queries (default)
server = GraphQLMCP.from_api(api, allow_mutations=False)

# Expose both queries and mutations
server = GraphQLMCP.from_api(api, allow_mutations=True)
```

### Tool Naming

Tools are automatically named using `snake_case`:

- `hello` → `hello`
- `getUser` → `get_user`
- `addBook` → `add_book`

## Environment Variables

Recommended environment variables:

```bash
# Server configuration
MCP_HOST=0.0.0.0
MCP_PORT=8002
MCP_NAME="My API"

# GraphQL endpoint
GRAPHQL_URL=https://api.example.com/graphql
GRAPHQL_TOKEN=your_token_here

# Security
JWT_SECRET=your_jwt_secret
ALLOW_MUTATIONS=true
```

Use in your code:

```python
import os
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url=os.environ["GRAPHQL_URL"],
    bearer_token=os.environ.get("GRAPHQL_TOKEN"),
    name=os.environ.get("MCP_NAME", "GraphQL API"),
    allow_mutations=os.environ.get("ALLOW_MUTATIONS", "false").lower() == "true"
)
```

## Complete Example

Here's a complete production-ready configuration:

```python
import os
import uvicorn
from graphql_api import GraphQLAPI
from graphql_mcp.server import GraphQLMCP
from starlette.middleware.cors import CORSMiddleware

# Load environment variables
HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "8002"))
ALLOW_MUTATIONS = os.environ.get("ALLOW_MUTATIONS", "false").lower() == "true"

# Create API (your schema definition here)
api = GraphQLAPI(...)

# Create MCP server
server = GraphQLMCP.from_api(
    api,
    name=os.environ.get("MCP_NAME", "My API"),
    graphql_http=True,
    allow_mutations=ALLOW_MUTATIONS
)

# Create HTTP app
app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        log_level="info"
    )
```

## Next Steps

- Learn about [testing](testing/)
- Explore [examples](examples/)
- Check out the [API reference](api-reference/)
