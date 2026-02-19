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

