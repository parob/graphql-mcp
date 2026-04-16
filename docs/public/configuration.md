---
title: "Configuration"
---

# Configuration

## `@mcp` directive

The `@mcp` directive customizes how a GraphQL field or argument surfaces as an MCP tool.

| Arg | Type | Effect |
|-----|------|--------|
| `name` | `String` | Override the MCP tool/argument name (replaces the default `snake_case` derivation). |
| `description` | `String` | Override the MCP description (replaces the GraphQL field/argument description). |
| `hidden` | `Boolean` | When `true`, skip the field or argument from MCP registration entirely. |
| `readOnly` | `Boolean` | MCP tool annotation hint: tool does not modify its environment. Inferred as `true` for GraphQL queries. |
| `destructive` | `Boolean` | MCP tool annotation hint: may perform destructive updates. Meaningful only when `readOnly: false`. |
| `idempotent` | `Boolean` | MCP tool annotation hint: repeated calls with same args have no additional effect. Meaningful only when `readOnly: false`. |
| `openWorld` | `Boolean` | MCP tool annotation hint: tool interacts with an open world of external entities. |

Valid on `FIELD_DEFINITION` and `ARGUMENT_DEFINITION`. The underlying GraphQL schema is unchanged — the directive only affects what MCP exposes.

`@mcp` is a standard GraphQL directive — it works with any library whose schema carries the directive through to the final GraphQL AST (`ast_node.directives`). That covers graphql-api and anything built from SDL (Ariadne, `graphql.build_schema`). See the per-library examples below.

::: code-group
```python [graphql-api]
from typing import Annotated, Optional
from uuid import UUID
from graphql_api import GraphQLAPI, field
from graphql_mcp import GraphQLMCP, mcp

class MyAPI:
    @field(mutable=True)
    @mcp(name="make_item", description="Create an item for the current user.")
    def create_item(
        self,
        name: str,
        user_id: Annotated[Optional[UUID], mcp(hidden=True)] = None,
    ) -> str:
        return f"Created by {user_id}"

# Register the directive with your API
api = GraphQLAPI(root_type=MyAPI, directives=[mcp])
server = GraphQLMCP.from_api(api)
```

```python [Ariadne]
from ariadne import make_executable_schema, QueryType
from graphql_mcp import GraphQLMCP

type_defs = """
    directive @mcp(
        name: String
        description: String
        hidden: Boolean
    ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

    type Query {
        search(
            query: String!
            internalFlag: Boolean = false @mcp(hidden: true)
            debugMode: Boolean = false @mcp(hidden: true)
        ): String @mcp(name: "find", description: "Search the catalog.")
    }
"""

query = QueryType()

@query.field("search")
def resolve_search(_, info, query, internalFlag=False, debugMode=False):
    return query

schema = make_executable_schema(type_defs, query)
server = GraphQLMCP(schema=schema)
```

```python [graphql-core (SDL)]
from graphql import build_schema
from graphql_mcp import GraphQLMCP

schema = build_schema("""
    directive @mcp(
        name: String
        description: String
        hidden: Boolean
    ) on FIELD_DEFINITION | ARGUMENT_DEFINITION

    type Query {
        search(
            query: String!
            internalFlag: Boolean = false @mcp(hidden: true)
            debugMode: Boolean = false @mcp(hidden: true)
        ): String @mcp(name: "find")
    }
""")

server = GraphQLMCP(schema=schema)
```
:::

The MCP tool exposes only non-hidden fields and arguments. Overridden names replace the default `snake_case` derivation. When an argument is renamed, the outbound GraphQL query still uses the original argument name — translation happens automatically inside the tool wrapper.

::: warning Strawberry and Graphene
Strawberry and Graphene don't attach directive information to the graphql-core argument's `ast_node`, so `@mcp` applied through their Python APIs isn't currently picked up by graphql-mcp. See [Strawberry & Graphene](/strawberry-graphene) for three supported workarounds (rebuild + copy resolvers, rebuild via Ariadne, or context-based hiding).
:::

::: warning
Hidden arguments **must** have a default value. GraphQL MCP raises a `ValueError` at startup if a hidden argument has no default. Two fields renamed to the same MCP name also raise a `ValueError`.
:::

::: info Migrating from `@mcpHidden`
The previous `mcp_hidden` directive has been replaced by the unified `@mcp` directive. Replace `@mcpHidden` with `@mcp(hidden: true)` and the `mcp_hidden` Python export with `mcp(hidden=True)`.
:::

## Tool annotations

MCP tools can carry four standard annotation hints that tell clients (and LLMs) *how* a tool behaves — whether it's safe to auto-run, whether retrying is OK, whether it touches external systems. graphql-mcp exposes these via four optional keys on the `@mcp` directive:

| Key | Type | Meaning when `true` | Default applied by graphql-mcp |
|-----|------|---------------------|-------------------------------|
| `readOnly` | `Boolean` | The tool does not modify its environment. | **Queries: `true`**. Mutations: unset. |
| `destructive` | `Boolean` | May perform destructive updates (vs. additive-only). Meaningful only when `readOnly` is `false`. | Unset (MCP clients assume `true`). |
| `idempotent` | `Boolean` | Calling repeatedly with the same arguments has no additional effect. Meaningful only when `readOnly` is `false`. | Unset (MCP clients assume `false`). |
| `openWorld` | `Boolean` | Interacts with an "open world" of external entities (web search, third-party APIs). | Unset (MCP clients assume `true`). |

These flow through to the standard MCP `readOnlyHint` / `destructiveHint` / `idempotentHint` / `openWorldHint` annotations — clients that support them (Claude Desktop, LLM orchestrators, tool-use UIs) use them to decide whether to auto-confirm, retry, run in parallel, or prompt the user.

::: info Inference defaults
Most users never write these — graphql-mcp infers the safe, common case:

- **GraphQL queries → `readOnly: true`** (standard GraphQL semantics: queries don't modify state).
- **Mutations** get no inference — the MCP spec's "assume destructive, assume not idempotent" defaults already match normal mutation semantics.

You only need to write annotations for the *exceptions*: a query that has a side effect, a mutation that's idempotent, a field that does or doesn't hit an external service.
:::

### When to set each one

**`readOnly: false` on a query** — the query has a side effect the LLM/user should know about. Once you set this, the spec says `destructive` and `idempotent` become meaningful, so also set them explicitly.

```graphql
type Query {
    "Logs an access event when reading. Not strictly a pure query."
    user(
        id: ID!
    ): User @mcp(
        readOnly: false,
        destructive: false,   # logging an audit row isn't destructive
        idempotent: true      # repeated reads produce the same user
    )
}
```

**`idempotent: true` on a mutation** — setters, upserts, "ensure state" operations. Safe to retry.

```graphql
type Mutation {
    "Set a user's status. Calling twice with the same args is a no-op."
    setUserStatus(
        userId: ID!
        status: UserStatus!
    ): User @mcp(idempotent: true)
}
```

**`destructive: false` on a mutation** — purely additive operations that can't clobber or delete existing data.

```graphql
type Mutation {
    "Append a comment to a post. Never modifies existing comments."
    addComment(
        postId: ID!
        body: String!
    ): Comment @mcp(destructive: false, idempotent: false)
}
```

**`openWorld: false`** — the field only touches your own data, not external systems. Helps LLMs reason about blast radius.

```graphql
type Query {
    "Looks up a product by ID from our own catalog."
    product(id: ID!): Product @mcp(openWorld: false)
}
```

**`openWorld: true`** on a remote-proxy field — you're calling a third-party API and want that made explicit.

```graphql
type Query {
    "Searches the web via an external provider."
    webSearch(query: String!): [SearchResult!]! @mcp(openWorld: true)
}
```

### Python-side equivalents

Via `graphql-api`:

```python
from graphql_api import GraphQLAPI, field
from graphql_mcp import GraphQLMCP, mcp

class API:
    @field
    @mcp(read_only=False, destructive=False, idempotent=True)
    def user(self, id: str) -> "User":
        """Logs an access event when reading."""
        ...

    @field(mutable=True)
    @mcp(idempotent=True)
    def set_user_status(self, user_id: str, status: "UserStatus") -> "User":
        ...
```

Both `snake_case` (`read_only`, `open_world`) and `camelCase` (`readOnly`, `openWorld`) Python kwargs are accepted — they resolve to the same SDL key.

Via `apply_mcp()`:

```python
apply_mcp(
    schema,
    fields={
        "Query.user": {
            "read_only": False,
            "destructive": False,
            "idempotent": True,
        },
        "Mutation.setUserStatus": {"idempotent": True},
    },
)
```

### How the hints interact

Per the MCP spec:

> `destructiveHint` and `idempotentHint` are meaningful only when `readOnlyHint == false`.

graphql-mcp passes whatever you set **verbatim** — no silent drops, no contradiction errors. If you set `readOnly: true` and `destructive: true` together, both go on the wire and each client interprets them per spec.

If you override a query to `readOnly: false`, **don't forget to also set `destructive` explicitly** — otherwise the spec default kicks in and the client assumes your query is destructive.

### What clients actually do with these

- **Claude Desktop and similar**: may skip the confirmation prompt for `readOnlyHint: true` tools; prompt for destructive/open-world ones.
- **Agent frameworks**: may retry `idempotentHint: true` tools on transient failure; avoid parallel calls to destructive ones.
- **Logging / safety layers**: may audit/flag open-world and destructive calls.

::: warning Hints, not contracts
MCP clients **MUST** treat these as hints from an untrusted server — security-critical decisions shouldn't rely on them alone. Think of them as helping the LLM make good choices, not as a permission system.
:::

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

| Transport | Use Case |
|-----------|----------|
| `http` | Default. Works with all MCP clients. |
| `streamable-http` | Bidirectional communication. Use for streaming responses or long-running tools. |
| `sse` | Legacy protocol. Use only if your MCP client doesn't support HTTP transport. |

### Stateless Mode

For serverless or load-balanced deployments, disable session state:

```python
app = server.http_app(stateless_http=True)
```

::: tip When to use stateless mode
Serverless functions (Lambda, Cloud Run) and load balancers can't share session state between requests. Enable `stateless_http=True` in these environments so each request is self-contained.
:::

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

::: details Lifespan management
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
:::

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
