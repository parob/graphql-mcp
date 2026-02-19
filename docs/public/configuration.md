---
title: "Configuration"
---

# Configuration

## mcp_hidden

The `mcp_hidden` directive marks GraphQL arguments as hidden from MCP tools. The argument remains visible in the GraphQL schema but won't appear as an MCP tool parameter. Hidden arguments **must** have default values.

This is useful for arguments that should be populated server-side (e.g. from authentication context) rather than by the AI agent.

### With graphql-api

Use the `Annotated` type hint with the `mcp_hidden` marker:

```python
from typing import Annotated, Optional
from uuid import UUID
from graphql_api import GraphQLAPI, field
from graphql_mcp import GraphQLMCP, mcp_hidden

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

The MCP tool for `create_item` exposes only the `name` parameter. The `user_id` argument still exists in the GraphQL schema for direct API consumers.

**Rules:**
- Hidden arguments **must** have a default value
- Register the directive: `GraphQLAPI(..., directives=[mcp_hidden])`

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
from graphql_mcp import GraphQLMCP

schema = build_schema(type_defs)
server = GraphQLMCP(schema=schema)
```

## Controlling Mutations

By default, both queries and mutations are exposed as MCP tools. Disable mutation tools for read-only access:

```python
server = GraphQLMCP.from_api(api, allow_mutations=False)
```

## GraphQL HTTP Endpoint

The GraphQL HTTP endpoint (with GraphiQL and the MCP Inspector) is enabled by default. To serve MCP only:

```python
server = GraphQLMCP.from_api(api, graphql_http=False)
```

Pass additional configuration to the GraphQL HTTP endpoint:

```python
server = GraphQLMCP(
    schema=schema,
    graphql_http_kwargs={"introspection": False}
)
```

## Transport

The `transport` parameter controls the MCP transport protocol:

```python
# Default HTTP transport
app = server.http_app(transport="http")

# Streamable HTTP (bidirectional)
app = server.http_app(transport="streamable-http")

# Server-Sent Events
app = server.http_app(transport="sse")
```

### Stateless Mode

For serverless or load-balanced deployments, disable session state:

```python
app = server.http_app(stateless_http=True)
```

## Authentication

GraphQL MCP supports JWT authentication via [FastMCP](https://gofastmcp.com/):

```python
from fastmcp.server.auth.providers.jwt import JWTVerifier
from graphql_mcp import GraphQLMCP

jwt_verifier = JWTVerifier(
    jwks_uri="https://your-auth0-domain/.well-known/jwks.json",
    issuer="https://your-auth0-domain/",
    audience="your-api-audience"
)

server = GraphQLMCP.from_api(api, auth=jwt_verifier)
```

When JWT is configured, both MCP and GraphQL HTTP endpoints are protected.

For remote APIs, see [token forwarding](/existing-apis#token-forwarding).

## Middleware

Add ASGI middleware when creating the HTTP application:

```python
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

app = server.http_app(
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"])
    ]
)
```

## Lifespan Management

When mounting the MCP app inside another Starlette application, enter its lifespan context for proper session management:

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

## Multi-API Servers

Serve multiple GraphQL APIs as different MCP servers:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from graphql_mcp import GraphQLMCP

books_server = GraphQLMCP.from_api(books_api, name="Books")
users_server = GraphQLMCP.from_api(users_api, name="Users")

app = Starlette(routes=[
    Mount("/mcp/books", app=books_server.http_app()),
    Mount("/mcp/users", app=users_server.http_app()),
])
```
