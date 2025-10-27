---
title: Getting Started
weight: 1
---

# Getting Started with GraphQL MCP

This guide will walk you through installing GraphQL MCP and creating your first MCP server.

## Installation

Install GraphQL MCP along with graphql-api:

```bash
pip install graphql-mcp graphql-api
```

You'll also need an ASGI server like uvicorn:

```bash
pip install uvicorn
```

## Your First MCP Server

Let's create a simple MCP server that exposes a GraphQL API:

```python
import uvicorn
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

# Define your GraphQL API
class GreetingAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"

    @field
    def goodbye(self, name: str = "World") -> str:
        """Say goodbye to someone."""
        return f"Goodbye, {name}!"

# Create the GraphQL API
api = GraphQLAPI(root_type=GreetingAPI)

# Create the MCP server
server = GraphQLMCP.from_api(api, name="Greeting Service")

# Create HTTP application
app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Testing Your Server

Run your server:

```bash
python app.py
```

Your MCP server is now running on `http://localhost:8002`.

### Using the MCP Inspector

If you enable the GraphQL HTTP endpoint, you can access the built-in MCP Inspector:

```python
server = GraphQLMCP.from_api(
    api,
    name="Greeting Service",
    graphql_http=True  # Enable GraphQL HTTP endpoint
)
```

Navigate to `http://localhost:8002` in your browser to access the inspector.

## Next Steps

- Learn about [connecting to remote GraphQL APIs](remote-graphql/)
- Explore [authentication options](authentication/)
- See more [examples](examples/)
