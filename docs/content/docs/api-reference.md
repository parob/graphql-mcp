---
title: "API Reference"
weight: 6
---

# API Reference

Complete API documentation for GraphQL MCP.

## GraphQLMCP

Main class for creating MCP servers from GraphQL schemas. Extends [FastMCP](https://gofastmcp.com/).

### Constructor

```python
GraphQLMCP(
    schema: GraphQLSchema,
    graphql_http: bool = True,
    graphql_http_kwargs: Optional[Dict[str, Any]] = None,
    allow_mutations: bool = True,
    *args, **kwargs  # Forwarded to FastMCP (name, auth, etc.)
)
```

**Parameters:**

- `schema` (GraphQLSchema): The GraphQL schema to generate tools from
- `graphql_http` (bool): Enable GraphQL HTTP endpoint and inspector. Default: `True`
- `graphql_http_kwargs` (Optional[Dict[str, Any]]): Additional keyword arguments passed to `GraphQLHTTP` when `graphql_http` is enabled
- `allow_mutations` (bool): Generate tools for GraphQL mutations. Default: `True`
- `*args, **kwargs`: Forwarded to FastMCP. Common kwargs include:
  - `name` (str): Display name for the MCP server
  - `auth` (OAuthProvider | JWTVerifier): Authentication configuration

**Example:**

```python
from graphql import GraphQLSchema
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP(
    schema=my_schema,
    name="My API",
    graphql_http=True
)
```

### Class Methods

#### from_api

Create server from a [graphql-api](https://graphql-api.parob.com/) instance. Requires `graphql-api` to be installed.

```python
@classmethod
def from_api(
    cls,
    api: GraphQLAPI,
    graphql_http: bool = True,
    allow_mutations: bool = True,
    *args, **kwargs  # Forwarded to FastMCP (name, auth, etc.)
) -> GraphQLMCP
```

**Parameters:**

- `api` (GraphQLAPI): The GraphQL API instance
- `graphql_http` (bool): Enable GraphQL HTTP endpoint. Default: `True`
- `allow_mutations` (bool): Generate mutation tools. Default: `True`
- `*args, **kwargs`: Forwarded to FastMCP (e.g. `name`, `auth`)

**Returns:** GraphQLMCP instance

**Example:**

```python
from graphql_api import GraphQLAPI
from graphql_mcp.server import GraphQLMCP

api = GraphQLAPI(root_type=MyAPI)
server = GraphQLMCP.from_api(
    api,
    name="My Service",
    graphql_http=True
)
```

#### from_remote_url

Create server from a remote GraphQL endpoint. Introspects the remote schema and generates MCP tools.

```python
@classmethod
def from_remote_url(
    cls,
    url: str,
    bearer_token: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 30,
    graphql_http: bool = True,
    graphql_http_kwargs: Optional[Dict[str, Any]] = None,
    allow_mutations: bool = True,
    forward_bearer_token: bool = False,
    verify_ssl: bool = True,
    *args, **kwargs  # Forwarded to FastMCP (name, auth, etc.)
) -> GraphQLMCP
```

**Parameters:**

- `url` (str): GraphQL endpoint URL
- `bearer_token` (Optional[str]): Static bearer token for authentication with the remote server
- `headers` (Optional[Dict[str, str]]): Additional HTTP headers to include in requests
- `timeout` (int): Request timeout in seconds. Default: `30`
- `graphql_http` (bool): Enable GraphQL HTTP endpoint. Default: `True`
- `graphql_http_kwargs` (Optional[Dict[str, Any]]): Additional keyword arguments for `GraphQLHTTP`
- `allow_mutations` (bool): Generate mutation tools. Default: `True`
- `forward_bearer_token` (bool): Forward incoming MCP request bearer tokens to the remote server. Default: `False`. **Security warning:** when enabled, client authentication tokens are shared with the remote server. Only enable if you trust the remote server completely. Use HTTPS.
- `verify_ssl` (bool): Whether to verify SSL certificates. Default: `True`. Set to `False` only for development with self-signed certificates.
- `*args, **kwargs`: Forwarded to FastMCP (e.g. `name`, `auth`)

**Returns:** GraphQLMCP instance

**Example:**

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_token",
    headers={"X-Custom": "value"},
    timeout=60,
    allow_mutations=False,
    name="GitHub"
)
```

### Instance Methods

#### http_app

Create an ASGI HTTP application for serving the MCP server.

```python
def http_app(
    self,
    path: str | None = None,
    middleware: list | None = None,
    json_response: bool | None = None,
    stateless_http: bool | None = None,
    transport: Literal["http", "streamable-http", "sse"] = "http",
    graphql_http: Optional[bool] = None,
    graphql_http_kwargs: Optional[Dict[str, Any]] = None,
    **kwargs
) -> StarletteWithLifespan
```

**Parameters:**

- `path` (str | None): Base URL path for MCP endpoints
- `middleware` (list | None): Additional ASGI middleware to add to the application
- `json_response` (bool | None): Use JSON response format
- `stateless_http` (bool | None): Disable session state management. Recommended for serverless and load-balanced deployments
- `transport` (str): MCP transport type. Default: `"http"`. Options: `"http"`, `"streamable-http"`, `"sse"`
- `graphql_http` (Optional[bool]): Override the instance's `graphql_http` setting
- `graphql_http_kwargs` (Optional[Dict[str, Any]]): Override the instance's `graphql_http_kwargs`
- `**kwargs`: Additional keyword arguments for FastMCP

**Returns:** `StarletteWithLifespan` ASGI application

> **Lifespan management:** When mounting the returned app inside another Starlette application, you must enter its lifespan context. See [Lifespan Management](../configuration/#lifespan-management).

**Example:**

```python
app = server.http_app(
    transport="streamable-http",
    stateless_http=True,
)
```

## mcp_hidden

Directive for hiding GraphQL arguments from MCP tools. The argument remains in the GraphQL schema but is not exposed as an MCP tool parameter.

See [mcp_hidden Directive](../configuration/#mcp_hidden-directive) for full documentation and examples.

```python
from graphql_mcp import mcp_hidden
```

## JWTVerifier

JWT authentication verifier from [FastMCP](https://gofastmcp.com/).

```python
from fastmcp.server.auth.providers.jwt import JWTVerifier
```

### Constructor

```python
JWTVerifier(
    jwks_uri: str = None,
    public_key: str = None,
    algorithm: str = "RS256",
    issuer: str = None,
    audience: str = None,
)
```

**Parameters:**

- `jwks_uri` (str): JWKS endpoint URL (for RS256/asymmetric keys)
- `public_key` (str): Public key or shared secret (for HS256/symmetric keys)
- `algorithm` (str): Signing algorithm. Default: `"RS256"`
- `issuer` (str): Expected token issuer
- `audience` (str): Expected token audience

**Examples:**

```python
from fastmcp.server.auth.providers.jwt import JWTVerifier

# Production: JWKS (asymmetric)
verifier = JWTVerifier(
    jwks_uri="https://auth.example.com/.well-known/jwks.json",
    issuer="https://auth.example.com/",
    audience="my-api"
)

# Development: shared secret (symmetric)
verifier = JWTVerifier(
    public_key="dev-secret",
    algorithm="HS256",
    issuer="local-dev",
    audience="my-api"
)

# Pass to GraphQLMCP
server = GraphQLMCP.from_api(api, auth=verifier)
```

## Type Mappings

GraphQL MCP automatically maps GraphQL types to Python/MCP types:

### Scalar Types

| GraphQL Type | Python Type |
|---|---|
| String | `str` |
| Int | `int` |
| Float | `float` |
| Boolean | `bool` |
| ID | `str` |

### Custom Scalars (graphql-api)

These are available when using [graphql-api](https://graphql-api.parob.com/):

| GraphQL Type | Python Type |
|---|---|
| UUID | `uuid.UUID` |
| DateTime | `datetime` |
| Date | `date` |
| JSON | `dict` |
| Bytes | `bytes` |

### Composite Types

| GraphQL Type | Python/MCP Type |
|---|---|
| `[Type]` | `list[Type]` |
| `Type!` | Required (non-optional) |
| Input Object | Pydantic model (dynamically generated) |
| Object Type | Pydantic model (dynamically generated) |
| Enum (string) | `Literal[values]` with case-insensitive validation |
| Enum (integer) | `Union[Literal[int_values], Literal[string_names]]` |

> **Enum handling:** Enum values are validated case-insensitively. Both enum names (e.g. `ASSISTANT`) and values (e.g. `assistant`) are accepted.

> **Input/Output objects:** GraphQL input and output object types are automatically converted to Pydantic models with proper field types, descriptions, and required/optional markers.

## Endpoints

When using `http_app()`, the following endpoints are available:

- `POST /mcp` — MCP protocol endpoint
- `GET /graphql` — GraphiQL interface with MCP Inspector (when `graphql_http=True`)
- `POST /graphql` — GraphQL HTTP endpoint (when `graphql_http=True`)

### Tool Format

Each GraphQL field becomes an MCP tool with snake_case naming:

```json
{
  "name": "add_book",
  "description": "Add a new book to the store.",
  "inputSchema": {
    "type": "object",
    "properties": {
      "title": {"type": "string"},
      "author": {"type": "string"}
    },
    "required": ["title", "author"]
  }
}
```

## Common Environment Variable Patterns

GraphQL MCP does not read environment variables directly. These are common patterns for configuring your server:

```python
import os

server = GraphQLMCP.from_remote_url(
    url=os.getenv("GRAPHQL_URL"),
    bearer_token=os.getenv("GRAPHQL_TOKEN"),
    name=os.getenv("SERVICE_NAME", "GraphQL API")
)
```

| Variable | Usage |
|---|---|
| `GRAPHQL_URL` | GraphQL endpoint URL |
| `GRAPHQL_TOKEN` | Bearer token |
| `PORT` | Server port |
| `HOST` | Server host |
| `LOG_LEVEL` | Logging level (for uvicorn) |

## Next Steps

- **[Examples](../examples/)** — See the API in action
- **[Configuration](../configuration/)** — Learn about all options
- **[GitHub Repository](https://github.com/parob/graphql-mcp)** — View source code
