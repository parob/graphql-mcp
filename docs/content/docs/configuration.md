---
title: "Configuration"
weight: 2
---

# Configuration

GraphQL MCP provides flexible configuration options for customizing your MCP server behavior.

## Server Creation

### From Schema (Universal)

Works with **any** GraphQL library that produces a `graphql-core` schema (Strawberry, Ariadne, Graphene, graphql-api, etc.):

```python
from graphql import GraphQLSchema
from graphql_mcp.server import GraphQLMCP

# Your schema from Strawberry, Ariadne, Graphene, or any library
schema = GraphQLSchema(...)

server = GraphQLMCP(
    schema=schema,
    name="My API",
    allow_mutations=True,
    auth=None
)
```

**Examples with popular libraries:**

```python
# Strawberry
import strawberry
schema = strawberry.Schema(query=Query)
server = GraphQLMCP(schema=schema._schema, name="My API")

# Ariadne
from ariadne import make_executable_schema
schema = make_executable_schema(type_defs, resolvers)
server = GraphQLMCP(schema=schema, name="My API")

# Graphene
import graphene
schema = graphene.Schema(query=Query)
server = GraphQLMCP(schema=schema.graphql_schema, name="My API")
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

### From graphql-api (Recommended for New Projects)

If you're building a new GraphQL API, [graphql-api](https://graphql-api.parob.com/) provides a clean decorator-based approach:

```python
from graphql_api import GraphQLAPI
from graphql_mcp.server import GraphQLMCP

api = GraphQLAPI(root_type=MyAPI)
server = GraphQLMCP.from_api(
    api,
    name="My API",
    allow_mutations=True,
    auth=None
)
```

> **Learn more**: See the [graphql-api documentation](https://graphql-api.parob.com/) for building GraphQL APIs with decorators.

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

The display name for your MCP server. Passed through to FastMCP via `**kwargs`.

```python
server = GraphQLMCP(schema=schema, name="Books API")
```

#### graphql_http
**Type:** `bool`
**Default:** `True`

Whether to enable the GraphQL HTTP endpoint alongside MCP. When enabled, your server provides both MCP and GraphQL HTTP interfaces.

```python
# Disable GraphQL HTTP endpoint (MCP only)
server = GraphQLMCP.from_api(api, graphql_http=False)
```

When enabled:
- GraphQL queries can be sent to `/graphql`
- GraphiQL interface is available in the browser
- MCP Inspector is automatically injected

> **Learn more**: See [graphql-http documentation](https://graphql-http.parob.com/) for details on GraphQL HTTP serving.

#### graphql_http_kwargs
**Type:** `Optional[Dict[str, Any]]`
**Default:** `None`

Additional keyword arguments passed to `GraphQLHTTP` when `graphql_http` is enabled. Useful for configuring the GraphQL HTTP endpoint.

```python
server = GraphQLMCP(
    schema=schema,
    graphql_http_kwargs={"introspection": False}
)
```

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

JWT authentication configuration for protected endpoints. Passed through to FastMCP via `**kwargs`.

```python
from fastmcp.server.auth.providers.jwt import JWTVerifier

jwt_verifier = JWTVerifier(
    jwks_uri="https://auth.example.com/.well-known/jwks.json",
    issuer="https://auth.example.com/",
    audience="my-api"
)

server = GraphQLMCP.from_api(api, auth=jwt_verifier)
```

> **Learn more**: See [graphql-http authentication docs](https://graphql-http.parob.com/docs/authentication/) for comprehensive authentication guides.

## mcp_hidden Directive

The `mcp_hidden` directive marks GraphQL arguments as hidden from MCP tools. The argument remains visible in the GraphQL schema but won't appear as an MCP tool parameter. Hidden arguments **must** have default values.

This is useful for arguments that should be populated server-side (e.g. from authentication context) rather than by the AI agent.

### With graphql-api

Use the `Annotated` type hint with the `mcp_hidden` marker:

```python
from typing import Annotated, Optional
from uuid import UUID
from graphql_api import GraphQLAPI, field
from graphql_mcp import mcp_hidden

class MyAPI:
    @field(mutable=True)
    def create_item(
        self,
        name: str,
        user_id: Annotated[Optional[UUID], mcp_hidden] = None,
    ) -> str:
        """Create an item. user_id is auto-filled from auth context."""
        return f"Created by {user_id}"

# Register the directive with your API
api = GraphQLAPI(root_type=MyAPI, directives=[mcp_hidden])
server = GraphQLMCP.from_api(api)
```

The MCP tool for `create_item` will only expose the `name` parameter. The `user_id` argument still exists in the GraphQL schema and can be used by direct GraphQL clients.

### With SDL (Any Library)

Define the `@mcpHidden` directive in your schema definition:

```graphql
directive @mcpHidden on ARGUMENT_DEFINITION

type Query {
    search(
        query: String!
        internalFlag: Boolean = false @mcpHidden
        debugMode: Boolean = false @mcpHidden
    ): String
}
```

Then use GraphQLMCP as normal — hidden arguments are detected automatically:

```python
from graphql import build_schema
from graphql_mcp.server import GraphQLMCP

schema = build_schema(type_defs)
server = GraphQLMCP(schema=schema)
```

## HTTP Application Configuration

The `http_app()` method creates an ASGI application for serving MCP:

```python
app = server.http_app(
    transport="streamable-http",
    stateless_http=True,
)
```

### Parameters

#### transport
**Type:** `str`
**Default:** `"http"`
**Options:** `"http"`, `"sse"`, `"streamable-http"`

The MCP transport protocol to use:

- `http` — Standard HTTP request/response (default)
- `sse` — Server-Sent Events for streaming
- `streamable-http` — HTTP with streaming support

```python
# Use streamable HTTP for streaming support
app = server.http_app(transport="streamable-http")
```

#### stateless_http
**Type:** `bool | None`
**Default:** `None`

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
**Type:** `str | None`
**Default:** `None`

The base URL path for MCP endpoints.

```python
# Custom path
app = server.http_app(path="/api/mcp")
```

#### middleware
**Type:** `list | None`
**Default:** `None`

Additional ASGI middleware to include in the application.

```python
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

app = server.http_app(
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"])
    ]
)
```

You can also add middleware after creation:

```python
app = server.http_app()
server.add_middleware(MyCustomMiddleware)
```

### Lifespan Management

When mounting the MCP app inside another Starlette application, you must enter its lifespan context for proper session management:

```python
from contextlib import asynccontextmanager, AsyncExitStack
from starlette.applications import Starlette
from starlette.routing import Mount

mcp_app = server.http_app(stateless_http=True)

@asynccontextmanager
async def lifespan(app: Starlette):
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(mcp_app.lifespan(app))
        yield

app = Starlette(
    routes=[Mount("/mcp", app=mcp_app)],
    lifespan=lifespan,
)
```

## Remote GraphQL Configuration

When connecting to remote GraphQL APIs:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_your_token_here",
    name="GitHub API",
    headers={"X-Custom-Header": "value"},
    timeout=60,
    allow_mutations=False,
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

Static bearer token for authentication with the remote server.

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

#### timeout
**Type:** `int`
**Default:** `30`

Request timeout in seconds.

```python
server = GraphQLMCP.from_remote_url(
    url="https://slow-api.example.com/graphql",
    timeout=60
)
```

#### allow_mutations
**Type:** `bool`
**Default:** `True`

Whether to generate MCP tools for mutations.

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    allow_mutations=False  # Read-only
)
```

#### forward_bearer_token
**Type:** `bool`
**Default:** `False`

Forward incoming MCP request bearer tokens to the remote GraphQL server. This is distinct from the static `bearer_token` parameter — it forwards the **client's** token from each MCP request.

> **Security warning:** When enabled, client authentication tokens are shared with the remote server. Only enable if you trust the remote server completely. Always use HTTPS for the remote URL.

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.internal.example.com/graphql",
    forward_bearer_token=True
)
```

#### verify_ssl
**Type:** `bool`
**Default:** `True`

Whether to verify SSL certificates. Set to `False` only for development with self-signed certificates.

```python
# Development only
server = GraphQLMCP.from_remote_url(
    url="https://localhost:8443/graphql",
    verify_ssl=False
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
from fastmcp.server.auth.providers.jwt import JWTVerifier
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_api(
    api,
    name="Production API",
    graphql_http=False,  # Disable GraphiQL in production
    allow_mutations=True,
    auth=jwt_verifier    # Always use authentication
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

- **[Learn about remote GraphQL](remote-graphql/)** — Connect to existing APIs
- **[Explore the MCP Inspector](mcp-inspector/)** — Test your configuration
- **[Check out examples](examples/)** — See configuration in action
