---
title: "Getting Started"
weight: 1
---

# Getting Started with GraphQL MCP

GraphQL MCP makes it easy to expose GraphQL APIs as MCP (Model Context Protocol) tools that can be used by AI agents and other systems.

## Installation

Install GraphQL MCP using pip:

```bash
pip install graphql-mcp graphql-api
```

Or using UV (recommended):

```bash
uv add graphql-mcp graphql-api
```

## Your First MCP Server

Let's create a simple MCP server from a GraphQL API:

```python
import uvicorn
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

# 1. Define your GraphQL API
class HelloAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"

    @field
    def goodbye(self, name: str = "World") -> str:
        """Say goodbye to someone."""
        return f"Goodbye, {name}!"

# 2. Create a GraphQL API instance
api = GraphQLAPI(root_type=HelloAPI)

# 3. Create an MCP server from the API
server = GraphQLMCP.from_api(api, name="Greetings")

# 4. Create the HTTP application
mcp_app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)

# 5. Run the server
if __name__ == "__main__":
    uvicorn.run(mcp_app, host="0.0.0.0", port=8002)
```

Save this as `server.py` and run it:

```bash
python server.py
```

Your MCP server is now running on `http://localhost:8002`!

## What Just Happened?

1. **Defined a GraphQL API** - We created a simple API with two query fields
2. **Created MCP Server** - `GraphQLMCP.from_api()` analyzed the schema and generated MCP tools
3. **Configured HTTP** - Set up the HTTP transport for MCP communication
4. **Started Server** - Used Uvicorn to serve the MCP endpoints

## Testing Your Server

### Using the MCP Inspector

If you enable the GraphQL HTTP endpoint, you can use the built-in MCP Inspector:

```python
server = GraphQLMCP.from_api(
    api,
    name="Greetings",
    graphql_http=True  # Enable GraphQL and MCP Inspector
)

mcp_app = server.http_app()
```

Now visit `http://localhost:8002/graphql` in your browser to access the inspector interface.

### Using an MCP Client

You can also test with any MCP client. Here's an example using the MCP Python SDK:

```python
from mcp import ClientSession
from mcp.client.stdio import stdio_client

async def test_mcp():
    async with stdio_client() as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize connection
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(f"Available tools: {tools}")

            # Call a tool
            result = await session.call_tool("hello", arguments={"name": "Alice"})
            print(f"Result: {result}")

import asyncio
asyncio.run(test_mcp())
```

## Next Steps

Now that you have a basic server running, you can:

- **[Learn about configuration options](configuration/)** - Customize your server
- **[Connect to remote GraphQL APIs](remote-graphql/)** - Expose existing APIs
- **[Explore the MCP Inspector](mcp-inspector/)** - Debug and test your tools
- **[Check out examples](examples/)** - See real-world usage patterns

## Common Patterns

### Adding Authentication

```python
from graphql_mcp.auth import JWTVerifier

# Create JWT verifier
jwt_verifier = JWTVerifier(
    jwks_uri="https://your-auth0-domain/.well-known/jwks.json",
    issuer="https://your-auth0-domain/",
    audience="your-api-audience"
)

# Pass to server
server = GraphQLMCP.from_api(
    api,
    auth=jwt_verifier
)
```

### Enabling Both GraphQL and MCP

```python
server = GraphQLMCP.from_api(
    api,
    graphql_http=True,  # Enable GraphQL HTTP endpoint
    name="My API"
)
```

### Controlling Mutations

```python
# Disable mutation tools (only expose queries)
server = GraphQLMCP.from_api(
    api,
    allow_mutations=False
)
```

## Troubleshooting

### Server won't start

Make sure all dependencies are installed:

```bash
pip install graphql-mcp graphql-api uvicorn
```

### Tools not appearing

Check that your GraphQL fields are properly decorated with `@field` and that they have docstrings. The tool names and descriptions come from your GraphQL schema.

### Type errors

GraphQL MCP automatically maps GraphQL types to Python types. If you encounter type errors, ensure your type hints match your GraphQL schema definitions.
