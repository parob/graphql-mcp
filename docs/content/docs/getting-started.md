---
title: "Getting Started"
weight: 1
---

# Getting Started with GraphQL MCP

GraphQL MCP makes it easy to expose GraphQL APIs as MCP (Model Context Protocol) tools that can be used by AI agents and other systems.

**Works with ANY GraphQL library**: Strawberry, Ariadne, Graphene, graphql-api, or any library using graphql-core.

## Installation

Install GraphQL MCP:

```bash
pip install graphql-mcp
```

Or using UV (recommended):

```bash
uv add graphql-mcp
```

## Prerequisites

GraphQL MCP works with any GraphQL schema from popular libraries:

- **[Strawberry](https://strawberry.rocks/)** - Modern, type-hint based GraphQL
- **[Ariadne](https://ariadnegraphql.org/)** - Schema-first GraphQL
- **[Graphene](https://graphene-python.org/)** - Code-first GraphQL
- **[graphql-api](https://graphql-api.parob.com/)** - Decorator-based GraphQL (recommended for new projects)
- **Any library** that produces a `graphql-core` schema

## Your First MCP Server

Choose your preferred GraphQL library:

### With Strawberry

```python
import strawberry
import uvicorn
from graphql_mcp.server import GraphQLMCP

# 1. Define your GraphQL schema with Strawberry
@strawberry.type
class Query:
    @strawberry.field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"

    @strawberry.field
    def goodbye(self, name: str = "World") -> str:
        """Say goodbye to someone."""
        return f"Goodbye, {name}!"

# 2. Create schema and MCP server
schema = strawberry.Schema(query=Query)
server = GraphQLMCP(schema=schema._schema, name="Greetings")

# 3. Create and run the HTTP application
app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

### With Ariadne

```python
from ariadne import make_executable_schema, QueryType
import uvicorn
from graphql_mcp.server import GraphQLMCP

# 1. Define your GraphQL schema with Ariadne
type_defs = """
    type Query {
        hello(name: String = "World"): String!
        goodbye(name: String = "World"): String!
    }
"""

query = QueryType()

@query.field("hello")
def resolve_hello(_, info, name="World"):
    return f"Hello, {name}!"

@query.field("goodbye")
def resolve_goodbye(_, info, name="World"):
    return f"Goodbye, {name}!"

# 2. Create schema and MCP server
schema = make_executable_schema(type_defs, query)
server = GraphQLMCP(schema=schema, name="Greetings")

# 3. Create and run the HTTP application
app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

### With graphql-api (Recommended for New Projects)

```python
from graphql_api import GraphQLAPI, field
import uvicorn
from graphql_mcp.server import GraphQLMCP

# 1. Define your GraphQL API with graphql-api
class HelloAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"

    @field
    def goodbye(self, name: str = "World") -> str:
        """Say goodbye to someone."""
        return f"Goodbye, {name}!"

# 2. Create GraphQL API and MCP server
api = GraphQLAPI(root_type=HelloAPI)
server = GraphQLMCP.from_api(api, name="Greetings")

# 3. Create and run the HTTP application
app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
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

The GraphQL HTTP endpoint and MCP Inspector are enabled by default (`graphql_http=True`). Just visit the GraphQL endpoint in your browser:

```
http://localhost:8002/graphql
```

The inspector interface will appear alongside GraphiQL. To disable it (e.g. in production):

```python
server = GraphQLMCP.from_api(
    api,
    name="Greetings",
    graphql_http=False  # Disable GraphQL endpoint and inspector
)
```

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

- **[How It Works](../how-it-works/)** - Understand how tools are generated from your schema
- **[Schema Design](../schema-design/)** - Design your schema for optimal MCP tools
- **[Learn about configuration options](configuration/)** - Customize your server
- **[Connect to remote GraphQL APIs](remote-graphql/)** - Expose existing APIs
- **[Explore the MCP Inspector](mcp-inspector/)** - Debug and test your tools
- **[Check out examples](examples/)** - See real-world usage patterns

## Common Patterns

### Adding Authentication

GraphQL MCP supports JWT authentication. For details on authentication configuration, see the [graphql-http authentication documentation](https://graphql-http.parob.com/docs/authentication/).

```python
from fastmcp.server.auth.providers.jwt import JWTVerifier

jwt_verifier = JWTVerifier(
    jwks_uri="https://your-auth0-domain/.well-known/jwks.json",
    issuer="https://your-auth0-domain/",
    audience="your-api-audience"
)

server = GraphQLMCP.from_api(api, auth=jwt_verifier)
```

### Enabling Both GraphQL and MCP

To serve both MCP tools and a GraphQL HTTP endpoint with GraphiQL:

```python
server = GraphQLMCP.from_api(
    api,
    graphql_http=True,  # Enables GraphQL endpoint
    name="My API"
)
```

Learn more about [GraphQL HTTP serving](https://graphql-http.parob.com/).

### Controlling Mutations

```python
server = GraphQLMCP.from_api(
    api,
    allow_mutations=False  # Only expose queries as tools
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
