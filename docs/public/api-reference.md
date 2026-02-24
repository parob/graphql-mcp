---
title: "API Reference"
---

# API Reference

## Concepts

### Tool Generation

Each top-level field in your GraphQL schema becomes an MCP tool:

- **Query fields** become read tools
- **Mutation fields** become write tools (when `allow_mutations=True`)

GraphQL field names (camelCase) are converted to snake_case for tool names: `getUser` becomes `get_user`, `addBook` becomes `add_book`.

Tool descriptions come from your GraphQL field descriptions (docstrings in graphql-api). Fields without descriptions produce tools with no description.

If a query and mutation share the same name, the **query takes precedence**.

#### Nested Tools

Beyond top-level fields, tools are also generated for nested field paths that have arguments at depth >= 2. For example, `user(id) { posts(limit) }` produces a `user_posts` tool. Parent field arguments are prefixed: `user_posts(user_id, limit)`.

### Type Mapping

| GraphQL | Python | Notes |
|---------|--------|-------|
| `String` | `str` | |
| `Int` | `int` | |
| `Float` | `float` | |
| `Boolean` | `bool` | |
| `ID` | `str` | |
| `UUID` | `uuid.UUID` | graphql-api only |
| `DateTime` | `datetime` | graphql-api only |
| `Date` | `date` | graphql-api only |
| `JSON` | `dict` | graphql-api only |
| `Bytes` | `bytes` | graphql-api only |
| `Type!` (non-null) | `T` | Required parameter |
| `Type` (nullable) | `Optional[T]` | Optional parameter |
| `[Type!]!` | `list[T]` | |
| Enum | `Literal[values]` | Case-insensitive — accepts both names and values |
| Input Object | Pydantic model | Dynamic model with proper field types |

### Selection Sets

When a tool returns an object type, graphql-mcp builds a selection set automatically:

- Only scalar fields are selected
- Nested objects are traversed up to **5 levels deep** (local) or **2 levels deep** (remote)
- Circular type references are detected and stopped
- If an object has no scalar fields, `__typename` is returned

### Local vs Remote Execution

**Local** (`GraphQLMCP(schema=...)` or `from_api()`): Tools execute GraphQL directly via graphql-core. Bearer tokens are available through FastMCP's Context.

**Remote** (`from_remote_url()`): Tools forward queries to the remote server via HTTP. The schema is introspected once at startup. `null` values for array fields are converted to `[]` for MCP validation. Unused variables are removed from queries. Bearer tokens are **not** forwarded unless `forward_bearer_token=True`.

---

## `GraphQLMCP`

```python
from graphql_mcp import GraphQLMCP
```

The main class for creating MCP servers from GraphQL schemas. Extends [FastMCP](https://gofastmcp.com/).

### `GraphQLMCP.__init__`

```python
GraphQLMCP.__init__(
    schema: GraphQLSchema,
    graphql_http: bool = True,
    graphql_http_kwargs: Optional[Dict[str, Any]] = None,
    allow_mutations: bool = True,
    *args,
    **kwargs,
)
```

Initialize GraphQLMCP server.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `schema` | `GraphQLSchema` | *required* | GraphQL schema to expose as MCP tools |
| `graphql_http` | `bool` | `True` | Whether to enable GraphQL HTTP endpoint |
| `graphql_http_kwargs` | `Optional[Dict[str, Any]]` | `None` | Additional kwargs for GraphQL HTTP |
| `allow_mutations` | `bool` | `True` | Whether to expose mutations as tools |
| `*args` | | |  |
| `**kwargs` | | |  |


### `GraphQLMCP.from_api`

```python
GraphQLMCP.from_api(
    api: GraphQLAPI,
    graphql_http: bool = True,
    allow_mutations: bool = True,
    *args,
    **kwargs,
)
```

Create a GraphQLMCP server from a graphql-api instance. Requires the ``graphql-api`` package to be installed.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `api` | `GraphQLAPI` | *required* | The GraphQLAPI instance to expose as MCP tools. |
| `graphql_http` | `bool` | `True` | Whether to enable the GraphQL HTTP endpoint (default: True). |
| `allow_mutations` | `bool` | `True` | Whether to expose mutation fields as MCP tools (default: True). |
| `*args` | | | Additional positional arguments forwarded to FastMCP. |
| `**kwargs` | | | Additional keyword arguments forwarded to FastMCP (e.g. ``name``, ``auth``). |

**Returns:** `GraphQLMCP` — A server instance with tools generated from the API schema.


### `GraphQLMCP.from_remote_url`

```python
GraphQLMCP.from_remote_url(
    url: str,
    bearer_token: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    graphql_http: bool = True,
    graphql_http_kwargs: Optional[Dict[str, Any]] = None,
    allow_mutations: bool = True,
    forward_bearer_token: bool = False,
    verify_ssl: bool = True,
    *args,
    **kwargs,
)
```

Create a GraphQLMCP from a remote GraphQL endpoint.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | *required* | The GraphQL endpoint URL |
| `bearer_token` | `Optional[str]` | `None` | Optional Bearer token for authentication |
| `headers` | `Optional[Dict[str, str]]` | `None` | Optional additional headers to include in requests |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `graphql_http` | `bool` | `True` | Whether to enable GraphQL HTTP endpoint (default: True) |
| `graphql_http_kwargs` | `Optional[Dict[str, Any]]` | `None` | Optional keyword arguments to pass to GraphQLHTTP |
| `allow_mutations` | `bool` | `True` | Whether to expose mutations as tools (default: True) |
| `forward_bearer_token` | `bool` | `False` | Whether to forward bearer tokens from MCP requests to the remote GraphQL server (default: False). Only enable if you trust the remote server. Use HTTPS. |
| `verify_ssl` | `bool` | `True` | Whether to verify SSL certificates (default: True). Set to False only for development with self-signed certs. |
| `*args` | | | Additional arguments to pass to FastMCP |
| `**kwargs` | | | Additional keyword arguments to pass to FastMCP |

**Returns:** `GraphQLMCP` — A server instance with tools generated from the remote schema.


### `GraphQLMCP.http_app`

```python
GraphQLMCP.http_app(
    path: str | None = None,
    middleware: list[starlette.middleware.Middleware] | None = None,
    json_response: bool | None = None,
    stateless_http: bool | None = None,
    transport: Literal['http', 'streamable-http', 'sse'] = 'http',
    graphql_http: Optional[bool] = None,
    graphql_http_kwargs: Optional[Dict[str, Any]] = None,
    **kwargs,
) -> StarletteWithLifespan
```

Create an ASGI HTTP application for serving the MCP server. Extends FastMCP's ``http_app()`` to optionally mount a GraphQL HTTP
endpoint (with GraphiQL and the MCP Inspector) at ``/graphql``.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `path` | `str | None` | `None` | Base URL path for MCP endpoints. |
| `middleware` | `list[starlette.middleware.Middleware] | None` | `None` | Additional ASGI middleware to include. |
| `json_response` | `bool | None` | `None` | Use JSON response format. |
| `stateless_http` | `bool | None` | `None` | Disable session state. Set to True for serverless and load-balanced deployments. |
| `transport` | `Literal['http', 'streamable-http', 'sse']` | `'http'` | MCP transport protocol (default: ``"http"``). |
| `graphql_http` | `Optional[bool]` | `None` | Override this instance's ``graphql_http`` setting. |
| `graphql_http_kwargs` | `Optional[Dict[str, Any]]` | `None` | Override this instance's ``graphql_http_kwargs``. |
| `**kwargs` | | | Additional keyword arguments forwarded to FastMCP's ``http_app()``. |

**Returns:** `StarletteWithLifespan` — An ASGI application ready for ``uvicorn.run()``.


## `mcp_hidden`

```python
from graphql_mcp import mcp_hidden
```

A `SchemaDirective` that marks GraphQL arguments as hidden from MCP tools. The argument remains visible in the GraphQL schema but is not exposed as an MCP tool parameter.

Requires `graphql-api` to be installed. When `graphql-api` is not available, `mcp_hidden` is `None`.

See [Configuration](/configuration#mcp-hidden) for usage examples.

## Low-Level API

These functions are importable from `graphql_mcp.server` and `graphql_mcp.remote` but are not part of the primary public interface. Use them when you need fine-grained control over tool registration.

### `add_tools_from_schema`

```python
add_tools_from_schema(
    schema: GraphQLSchema,
    server: fastmcp.server.server.FastMCP | None = None,
    allow_mutations: bool = True,
) -> FastMCP
```

Populates a FastMCP server with tools for LOCAL GraphQL schema execution. This function creates tools that execute GraphQL operations directly against
the provided schema. Bearer token authentication is handled automatically
through the FastMCP Context object.

If a server instance is not provided, a new one will be created.
Processes mutations first, then queries, so that queries will overwrite
any mutations with the same name.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `schema` | `GraphQLSchema` | *required* | The GraphQLSchema to map. |
| `server` | `fastmcp.server.server.FastMCP | None` | `None` | An optional existing FastMCP server instance to add tools to. |
| `allow_mutations` | `bool` | `True` | Whether to expose mutations as tools (default: True). |

**Returns:** The populated FastMCP server instance.


### `add_tools_from_schema_with_remote`

```python
add_tools_from_schema_with_remote(
    schema: GraphQLSchema,
    server: FastMCP,
    remote_client: RemoteGraphQLClient,
    allow_mutations: bool = True,
    forward_bearer_token: bool = False,
) -> FastMCP
```

Populates a FastMCP server with tools for REMOTE GraphQL server execution. This function creates tools that forward GraphQL operations to a remote server
via the provided RemoteGraphQLClient. Unlike local schema execution, bearer
tokens are not automatically available and must be explicitly forwarded if needed.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `schema` | `GraphQLSchema` | *required* | The GraphQLSchema from the remote server |
| `server` | `FastMCP` | *required* | The FastMCP server instance to add tools to |
| `remote_client` | `RemoteGraphQLClient` | *required* | The remote GraphQL client for executing queries |
| `allow_mutations` | `bool` | `True` | Whether to expose mutations as tools (default: True) |
| `forward_bearer_token` | `bool` | `False` | Whether to forward bearer tokens from MCP requests to the remote server (default: False). Only relevant for remote servers - local schemas get token context automatically through FastMCP. |

**Returns:** The populated FastMCP server instance.


### `add_query_tools_from_schema`

```python
add_query_tools_from_schema(
    server: FastMCP,
    schema: GraphQLSchema,
)
```

Adds tools to a FastMCP server from the query fields of a GraphQL schema.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server` | `FastMCP` | *required* |  |
| `schema` | `GraphQLSchema` | *required* |  |


### `add_mutation_tools_from_schema`

```python
add_mutation_tools_from_schema(
    server: FastMCP,
    schema: GraphQLSchema,
)
```

Adds tools to a FastMCP server from the mutation fields of a GraphQL schema.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `server` | `FastMCP` | *required* |  |
| `schema` | `GraphQLSchema` | *required* |  |


### `RemoteGraphQLClient`

```python
from graphql_mcp.remote import RemoteGraphQLClient
```

### `RemoteGraphQLClient.__init__`

```python
RemoteGraphQLClient.__init__(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    bearer_token: Optional[str] = None,
    token_refresh_callback: Optional[Callable[[], str]] = None,
    verify_ssl: bool = True,
    undefined_strategy: str = 'remove',
    debug: bool = False,
)
```

Initialize a remote GraphQL client with schema introspection for type-aware transformations.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | *required* | The GraphQL endpoint URL |
| `headers` | `Optional[Dict[str, str]]` | `None` | Optional headers to include in requests |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `bearer_token` | `Optional[str]` | `None` | Optional Bearer token for authentication |
| `token_refresh_callback` | `Optional[Callable[[], str]]` | `None` | Optional callback to refresh the bearer token |
| `verify_ssl` | `bool` | `True` | Whether to verify SSL certificates (default: True, set to False for development) |
| `undefined_strategy` | `str` | `'remove'` | How to handle Undefined variables ("remove" or "null", default: "remove") |
| `debug` | `bool` | `False` | Enable verbose debug logging (default: False) |


### `RemoteGraphQLClient.execute`

```python
RemoteGraphQLClient.execute(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    retry_on_auth_error: bool = True,
) -> Dict[str, Any]
```

Execute a GraphQL query against the remote server.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | *required* | The GraphQL query string |
| `variables` | `Optional[Dict[str, Any]]` | `None` | Optional variables for the query |
| `operation_name` | `Optional[str]` | `None` | Optional operation name |
| `retry_on_auth_error` | `bool` | `True` | Whether to retry with refreshed token on 401/403 |

**Returns:** The GraphQL response data.


### `RemoteGraphQLClient.execute_with_token`

```python
RemoteGraphQLClient.execute_with_token(
    query: str,
    variables: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    retry_on_auth_error: bool = True,
    bearer_token_override: Optional[str] = None,
) -> Dict[str, Any]
```

Execute a GraphQL query with an optional bearer token override.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `query` | `str` | *required* | The GraphQL query string |
| `variables` | `Optional[Dict[str, Any]]` | `None` | Optional variables for the query |
| `operation_name` | `Optional[str]` | `None` | Optional operation name |
| `retry_on_auth_error` | `bool` | `True` | Whether to retry with refreshed token on 401/403 |
| `bearer_token_override` | `Optional[str]` | `None` | Optional bearer token to use instead of the client's token |

**Returns:** The GraphQL response data.


### `fetch_remote_schema`

```python
fetch_remote_schema(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    verify_ssl: bool = True,
) -> GraphQLSchema
```

Fetches a GraphQL schema from a remote server via introspection.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | *required* | The GraphQL endpoint URL |
| `headers` | `Optional[Dict[str, str]]` | `None` | Optional headers to include in the request (e.g., authorization) |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `verify_ssl` | `bool` | `True` | Whether to verify SSL certificates (default: True, set to False for development) |

**Returns:** `GraphQLSchema` — The fetched and built schema.


### `fetch_remote_schema_sync`

```python
fetch_remote_schema_sync(
    url: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    verify_ssl: bool = True,
) -> GraphQLSchema
```

Synchronous wrapper for fetching a remote GraphQL schema.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `url` | `str` | *required* | The GraphQL endpoint URL |
| `headers` | `Optional[Dict[str, str]]` | `None` | Optional headers to include in the request |
| `timeout` | `int` | `30` | Request timeout in seconds |
| `verify_ssl` | `bool` | `True` | Whether to verify SSL certificates (default: True, set to False for development) |

**Returns:** `GraphQLSchema` — The fetched and built schema.


---

## Release History

### 1.7

**1.7.7** — February 20, 2026 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.7.7/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.7.7)

Fix `model_dump()` serializing `None` for unset optional fields.

**1.7.6** — February 20, 2026 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.7.6/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.7.6)

Scope root pytest to `tests/` directory.

**1.7.5** — February 24, 2026 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.7.5/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.7.5)

Migrate docs from Hugo to VitePress. Add nested API examples and default GraphiQL queries. Fix MCP Inspector not updating URL on page navigation.

**1.7.4** — February 10, 2026 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.7.4/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.7.4)

Update enum validation — enum names are now accepted alongside values.

**1.7.3** — February 24, 2026 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.7.3/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.7.3)

Auto-create GitHub Release on tag push via CI.

**1.7.2** — February 24, 2026 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.7.2/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.7.2)

Fix case-insensitive enum validation for LLM tool calls.

**1.7.1** — December 16, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.7.1/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.7.1)

Add `@mcpHidden` directive for hiding GraphQL arguments from MCP tools.

**1.7.0** — December 9, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.7.0/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.7.0)

Add GitHub Pages documentation site and test examples.

**1.7.x highlights:** Documentation site with VitePress, `@mcpHidden` directive, case-insensitive enum validation, nested API examples, MCP Inspector URL navigation fix, optional field serialization fix.

### 1.6

**1.6.1** — October 28, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.6.1/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.6.1)

Version bump and project configuration update.

**1.6.0** — October 27, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.6.0/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.6.0)

Add `dict` type support and update graphql-http dependency.

**1.6.x highlights:** Dict type support, graphql-http dependency update.

### 1.5

**1.5.5** — October 7, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.5.5/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.5.5)

Linter fixes.

**1.5.4** — October 7, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.5.4/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.5.4)

Fix concurrency issues in tool execution.

**1.5.3** — October 7, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.5.3/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.5.3)

Patch release.

**1.5.2** — October 6, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.5.2/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.5.2)

Fix output schema generation for object types.

**1.5.1** — September 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.5.1/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.5.1)

MCP Inspector cleanup.

**1.5.0** — September 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.5.0/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.5.0)

Introduce MCP Inspector — an interactive tool testing UI injected into GraphiQL.

**1.5.x highlights:** MCP Inspector plugin, output schema fixes for object types, concurrency fixes in tool execution.

### 1.4

**1.4.1** — September 24, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.4.1/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.4.1)

Project configuration update.

**1.4.0** — September 24, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.4.0/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.4.0)

Code cleanup and reorganization.

**1.4.x highlights:** Internal cleanup and project configuration updates.

### 1.3

**1.3.24** — September 2, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.24/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.24)

Build and CI fixes.

**1.3.23** — September 2, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.23/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.23)

Warning removal and fixes.

**1.3.22** — August 29, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.22/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.22)

Internal renaming and cleanup.

**1.3.21** — August 29, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.21/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.21)

HTTP server updates.

**1.3.20** — August 27, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.20/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.20)

Fix enum return type handling.

**1.3.19** — August 27, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.19/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.19)

MCP tool generation fixes.

**1.3.18** — August 27, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.18/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.18)

Normalization fix for field names.

**1.3.17** — August 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.17/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.17)

Enum type handling fixes.

**1.3.16** — August 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.16/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.16)

Bug fix.

**1.3.15** — August 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.15/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.15)

Linter fixes.

**1.3.14** — August 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.14/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.14)

Internal updates.

**1.3.13** — August 14, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.13/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.13)

Add path redirect middleware.

**1.3.12** — August 14, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.12/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.12)

Restore GraphQL middleware support.

**1.3.11** — August 13, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.11/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.11)

Remove middleware layer.

**1.3.10** — August 13, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.10/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.10)

MCP tool generation fixes.

**1.3.9** — August 13, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.9/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.9)

Dependency and README updates.

**1.3.8** — August 12, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.8/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.8)

Add bearer token passthrough for remote APIs.

**1.3.7** — August 12, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.7/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.7)

Add `from_remote_url()` for connecting to remote GraphQL endpoints.

**1.3.6** — August 11, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.6/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.6)

Test fix.

**1.3.5** — August 11, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.5/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.5)

Test and linter fixes.

**1.3.4** — August 11, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.3.4/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.3.4)

Add enum type handling and various MCP fixes.

**1.3.x highlights:** Remote URL support via `from_remote_url()`, bearer token passthrough, enum type handling, path redirect middleware, GraphQL middleware refactoring.

### 1.1

**1.1.3** — August 10, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.1.3/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.1.3)

Add GraphQL HTTP server tests and MCP fixes.

**1.1.2** — August 6, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.1.2/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.1.2)

Mount GraphQL HTTP server by default when using `http_app()`.

**1.1.1** — July 15, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.1.1/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.1.1)

Test fixes for async execution.

**1.1.0** — February 24, 2026 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.1.0/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.1.0)

Add async execution support.

**1.1.x highlights:** Async execution, GraphQL HTTP server mounted by default on `http_app()`, GraphQL HTTP server tests.

### 1.0

**1.0.5** — July 1, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.0.5/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.0.5)

Add nested mutation support.

**1.0.4** — July 1, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.0.4/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.0.4)

Add MCP redirect middleware with tests.

**1.0.3** — June 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.0.3/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.0.3)

Bug fixes for tool generation.

**1.0.2** — June 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.0.2/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.0.2)

MCP tool generation updates.

**1.0.1** — June 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.0.1/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.0.1)

Add synchronous execution support.

**1.0.0** — June 26, 2025 &nbsp; [PyPI](https://pypi.org/project/graphql-mcp/1.0.0/) · [GitHub](https://github.com/parob/graphql-mcp/releases/tag/1.0.0)

Initial release of graphql-mcp. Generates MCP tools from graphql-core schemas — every query becomes a read tool, every mutation becomes a write tool.

**1.0.x highlights:** Synchronous execution, nested mutation support, MCP redirect middleware.
