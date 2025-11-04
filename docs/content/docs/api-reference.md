---
title: "API Reference"
weight: 6
---

# API Reference

Complete API documentation for GraphQL MCP.

## GraphQLMCP

Main class for creating MCP servers from GraphQL schemas.

### Constructor

```python
GraphQLMCP(
    schema: GraphQLSchema,
    name: str = "GraphQL MCP Server",
    graphql_http: bool = False,
    allow_mutations: bool = True,
    auth: Optional[JWTVerifier] = None
)
```

**Parameters:**

- `schema` (GraphQLSchema): The GraphQL schema to generate tools from
- `name` (str): Display name for the MCP server
- `graphql_http` (bool): Enable GraphQL HTTP endpoint and inspector
- `allow_mutations` (bool): Generate tools for mutations
- `auth` (Optional[JWTVerifier]): Authentication configuration

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

Create server from a graphql-api instance.

```python
@classmethod
def from_api(
    cls,
    api: GraphQLAPI,
    name: str = "GraphQL MCP Server",
    graphql_http: bool = False,
    allow_mutations: bool = True,
    auth: Optional[JWTVerifier] = None
) -> GraphQLMCP
```

**Parameters:**

- `api` (GraphQLAPI): The GraphQL API instance
- `name` (str): Display name for the server
- `graphql_http` (bool): Enable GraphQL HTTP endpoint
- `allow_mutations` (bool): Generate mutation tools
- `auth` (Optional[JWTVerifier]): Authentication config

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

Create server from a remote GraphQL endpoint.

```python
@classmethod
def from_remote_url(
    cls,
    url: str,
    bearer_token: Optional[str] = None,
    headers: Optional[dict] = None,
    name: str = "GraphQL MCP Server"
) -> GraphQLMCP
```

**Parameters:**

- `url` (str): GraphQL endpoint URL
- `bearer_token` (Optional[str]): Bearer token for authentication
- `headers` (Optional[dict]): Additional HTTP headers
- `name` (str): Display name for the server

**Returns:** GraphQLMCP instance

**Example:**

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_token",
    headers={"X-Custom": "value"},
    name="GitHub"
)
```

### Instance Methods

#### http_app

Create HTTP application for serving MCP.

```python
def http_app(
    self,
    transport: str = "streamable-http",
    stateless_http: bool = False,
    path: str = "/mcp"
) -> Starlette
```

**Parameters:**

- `transport` (str): MCP transport type ("http", "sse", "streamable-http")
- `stateless_http` (bool): Disable session state
- `path` (str): URL path for MCP endpoints

**Returns:** Starlette application

**Example:**

```python
app = server.http_app(
    transport="streamable-http",
    stateless_http=True,
    path="/api/mcp"
)
```

## JWTVerifier

JWT authentication verifier.

### Constructor

```python
JWTVerifier(
    jwks_uri: str,
    issuer: str,
    audience: str,
    algorithms: list[str] = ["RS256"]
)
```

**Parameters:**

- `jwks_uri` (str): JWKS endpoint URL
- `issuer` (str): Expected token issuer
- `audience` (str): Expected token audience
- `algorithms` (list[str]): Allowed signing algorithms

**Example:**

```python
from graphql_mcp.auth import JWTVerifier

verifier = JWTVerifier(
    jwks_uri="https://auth.example.com/.well-known/jwks.json",
    issuer="https://auth.example.com/",
    audience="my-api"
)
```

### Methods

#### verify

Verify a JWT token.

```python
def verify(self, token: str) -> dict
```

**Parameters:**

- `token` (str): JWT token to verify

**Returns:** Decoded token payload

**Raises:** `AuthenticationError` if verification fails

## Utility Functions

### snake_case

Convert string to snake_case.

```python
def snake_case(name: str) -> str
```

Used internally to convert GraphQL field names to Python function names.

**Example:**

```python
from graphql_mcp.utils import snake_case

snake_case("addBook")  # "add_book"
snake_case("getUser")  # "get_user"
```

## Type Mappings

GraphQL MCP automatically maps GraphQL types to Python types:

| GraphQL Type | Python Type |
|--------------|-------------|
| String | str |
| Int | int |
| Float | float |
| Boolean | bool |
| ID | str |
| [Type] | list[Type] |
| Type! | Type (required) |
| Custom Object | dict |
| Enum | str (enum value) |

## Error Types

### AuthenticationError

Raised when authentication fails.

```python
class AuthenticationError(Exception):
    pass
```

**Example:**

```python
from graphql_mcp.auth import AuthenticationError

try:
    verifier.verify(token)
except AuthenticationError as e:
    print(f"Auth failed: {e}")
```

### SchemaError

Raised when schema introspection or analysis fails.

```python
class SchemaError(Exception):
    pass
```

## Environment Variables

GraphQL MCP respects these environment variables:

- `GRAPHQL_URL` - Default GraphQL endpoint URL
- `GRAPHQL_TOKEN` - Default bearer token
- `LOG_LEVEL` - Logging level (DEBUG, INFO, WARNING, ERROR)
- `PORT` - Default server port
- `HOST` - Default server host

## MCP Protocol

GraphQL MCP implements the [Model Context Protocol](https://modelcontextprotocol.io/) specification.

### Supported Transports

- **HTTP** - Simple request/response
- **SSE** - Server-Sent Events for streaming
- **Streamable HTTP** - HTTP with streaming support (recommended)

### Endpoints

When using `http_app()`, the following endpoints are available:

- `POST /mcp` - MCP protocol endpoint
- `GET /graphql` - GraphiQL interface (if `graphql_http=True`)
- `POST /graphql` - GraphQL endpoint (if `graphql_http=True`)

### Tool Format

Each GraphQL field becomes an MCP tool:

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

## Next Steps

- **[Examples](examples/)** - See the API in action
- **[Configuration](configuration/)** - Learn about all options
- **[GitHub Repository](https://github.com/parob/graphql-mcp)** - View source code
