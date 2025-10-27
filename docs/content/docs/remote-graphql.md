---
title: Remote GraphQL APIs
weight: 2
---

# Connecting to Remote GraphQL APIs

GraphQL MCP can connect to any existing GraphQL API and expose it as MCP tools, making it easy to integrate external APIs into AI agent workflows.

## Basic Usage

Connect to a public GraphQL API:

```python
from graphql_mcp.server import GraphQLMCP

# Connect to a remote API
server = GraphQLMCP.from_remote_url(
    url="https://countries.trevorblades.com/",
    name="Countries API"
)

# Serve as HTTP endpoint
app = server.http_app()
```

## Authentication

### Bearer Token Authentication

For APIs that require authentication:

```python
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="your_github_token",
    name="GitHub API"
)
```

### Custom Headers

You can also pass custom headers:

```python
server = GraphQLMCP.from_remote_url(
    url="https://your-api.com/graphql",
    headers={
        "Authorization": "Bearer your_token",
        "X-Custom-Header": "value"
    },
    name="Custom API"
)
```

## Configuration Options

### Allowing Mutations

By default, only queries are exposed as tools. To enable mutations:

```python
server = GraphQLMCP.from_remote_url(
    url="https://your-api.com/graphql",
    allow_mutations=True,  # Enable mutation tools
    name="Writable API"
)
```

### GraphQL HTTP Endpoint

Enable a GraphQL HTTP endpoint alongside the MCP tools:

```python
server = GraphQLMCP.from_remote_url(
    url="https://your-api.com/graphql",
    graphql_http=True,  # Enable GraphQL endpoint with inspector
    name="Inspectable API"
)
```

## Complete Example

Here's a complete example with all options:

```python
import uvicorn
from graphql_mcp.server import GraphQLMCP

# Connect to GitHub's GraphQL API
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="ghp_your_token_here",
    name="GitHub API",
    allow_mutations=True,
    graphql_http=True
)

# Create HTTP app
app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Using with Other GraphQL Libraries

GraphQL MCP works with any GraphQL library that produces a `graphql-core` schema:

### Strawberry

```python
import strawberry
from graphql_mcp.server import GraphQLMCP

@strawberry.type
class Query:
    @strawberry.field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

schema = strawberry.Schema(query=Query)
server = GraphQLMCP(schema=schema._schema, name="Strawberry API")
```

### Ariadne

```python
from ariadne import make_executable_schema
from graphql_mcp.server import GraphQLMCP

type_defs = """
    type Query {
        hello(name: String = "World"): String!
    }
"""

schema = make_executable_schema(type_defs)
server = GraphQLMCP(schema=schema, name="Ariadne API")
```

## Next Steps

- Learn about [authentication and security](authentication/)
- Explore [configuration options](configuration/)
- See more [examples](examples/)
