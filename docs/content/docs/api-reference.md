---
title: API Reference
weight: 7
---

# API Reference

Complete reference for the GraphQL MCP API.

## GraphQLMCP

The main server class for creating MCP servers from GraphQL schemas.

### Constructor

```python
GraphQLMCP(
    schema: GraphQLSchema,
    name: str = "GraphQL MCP",
    graphql_http: bool = False,
    allow_mutations: bool = False,
    auth: Optional[Callable] = None
)
```

**Parameters:**

- `schema` (GraphQLSchema): The GraphQL schema to expose as MCP tools
- `name` (str): Display name for the MCP server (default: "GraphQL MCP")
- `graphql_http` (bool): Enable GraphQL HTTP endpoint with inspector (default: False)
- `allow_mutations` (bool): Expose mutations as MCP tools (default: False)
- `auth` (Optional[Callable]): Optional JWT authentication verifier

### Class Methods

#### from_api

Create an MCP server from a graphql-api API instance:

```python
@classmethod
def from_api(
    cls,
    api: GraphQLAPI,
    name: str = "GraphQL MCP",
    graphql_http: bool = False,
    allow_mutations: bool = False,
    auth: Optional[Callable] = None
) -> GraphQLMCP
```

**Example:**
```python
from graphql_api import GraphQLAPI
from graphql_mcp.server import GraphQLMCP

api = GraphQLAPI(root_type=MyAPI)
server = GraphQLMCP.from_api(api, name="My API")
```

#### from_remote_url

Create an MCP server from a remote GraphQL endpoint:

```python
@classmethod
def from_remote_url(
    cls,
    url: str,
    bearer_token: Optional[str] = None,
    headers: Optional[dict] = None,
    name: str = "GraphQL MCP",
    graphql_http: bool = False,
    allow_mutations: bool = False
) -> GraphQLMCP
```

**Parameters:**

- `url` (str): URL of the remote GraphQL endpoint
- `bearer_token` (Optional[str]): Bearer token for authentication
- `headers` (Optional[dict]): Custom headers to include in requests
- `name` (str): Display name for the MCP server
- `graphql_http` (bool): Enable GraphQL HTTP endpoint
- `allow_mutations` (bool): Expose mutations as tools

**Example:**
```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_token",
    name="GitHub API"
)
```

### Instance Methods

#### http_app

Create an ASGI HTTP application:

```python
def http_app(
    transport: str = "streamable-http",
    stateless_http: bool = True
) -> ASGIApp
```

**Parameters:**

- `transport` (str): Transport protocol - "streamable-http", "http", or "sse" (default: "streamable-http")
- `stateless_http` (bool): Whether to maintain client state (default: True)

**Returns:** ASGI application that can be served with uvicorn or other ASGI servers

**Example:**
```python
app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)
```

### Properties

#### name

Get or set the server name:

```python
server.name  # Get name
server.name = "New Name"  # Set name
```

#### schema

Access the underlying GraphQL schema:

```python
schema = server.schema
```

## Transport Options

### streamable-http

Recommended for most use cases. Supports streaming responses.

```python
app = server.http_app(transport="streamable-http")
```

### http

Standard HTTP with request/response model:

```python
app = server.http_app(transport="http")
```

### sse

Server-Sent Events for real-time updates:

```python
app = server.http_app(
    transport="sse",
    stateless_http=False  # SSE requires stateful connections
)
```

## Type Mapping

GraphQL types are automatically mapped to Python types:

| GraphQL Type | Python Type |
|-------------|-------------|
| String | str |
| Int | int |
| Float | float |
| Boolean | bool |
| ID | str |
| [String] | list[str] |
| String! | str (non-null) |
| CustomType | dict |
| [CustomType] | list[dict] |

## Tool Naming

GraphQL field names are converted to snake_case for MCP tools:

| GraphQL Field | MCP Tool Name |
|--------------|---------------|
| hello | hello |
| getUser | get_user |
| addBook | add_book |
| fetchUserData | fetch_user_data |

## Error Handling

GraphQL errors are returned in MCP tool results:

```python
{
    "data": null,
    "errors": [
        {
            "message": "Error message",
            "locations": [...],
            "path": [...]
        }
    ]
}
```

## Authentication

### Bearer Token

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    bearer_token="your_token"
)
```

### Custom Headers

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.example.com/graphql",
    headers={
        "Authorization": "Bearer token",
        "X-API-Key": "key"
    }
)
```

### JWT Verifier

```python
def jwt_verifier(token: str) -> dict:
    # Your JWT verification logic
    return decoded_payload

server = GraphQLMCP.from_api(api, auth=jwt_verifier)
```

## Environment Variables

Recommended environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| MCP_HOST | Server host | 0.0.0.0 |
| MCP_PORT | Server port | 8002 |
| MCP_NAME | Server display name | GraphQL MCP |
| GRAPHQL_URL | Remote GraphQL URL | - |
| GRAPHQL_TOKEN | Authentication token | - |
| ALLOW_MUTATIONS | Enable mutations | false |
| CORS_ORIGINS | CORS allowed origins | * |

## Examples

### Basic Server

```python
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

class MyAPI:
    @field
    def hello(self, name: str) -> str:
        return f"Hello, {name}!"

api = GraphQLAPI(root_type=MyAPI)
server = GraphQLMCP.from_api(api, name="My API")
app = server.http_app()
```

### Remote Server with Auth

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_token",
    name="GitHub",
    allow_mutations=True,
    graphql_http=True
)
app = server.http_app()
```

### Production Server

```python
import os
import uvicorn

server = GraphQLMCP.from_api(
    api,
    name=os.environ.get("MCP_NAME", "API"),
    graphql_http=True,
    allow_mutations=True
)

app = server.http_app(transport="streamable-http")

uvicorn.run(
    app,
    host=os.environ.get("MCP_HOST", "0.0.0.0"),
    port=int(os.environ.get("MCP_PORT", "8002")),
    workers=4
)
```

## Next Steps

- See practical [examples](examples/)
- Learn about [testing](testing/)
- Explore [configuration options](configuration/)
