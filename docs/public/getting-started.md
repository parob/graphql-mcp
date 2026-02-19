---
title: "Getting Started"
---

# Getting Started

## Installation

```bash
pip install graphql-mcp
```

Or with uv:

```bash
uv add graphql-mcp
```

## Your First MCP Server

```python
from graphql_api import GraphQLAPI, field
import uvicorn
from graphql_mcp import GraphQLMCP

class HelloAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"

api = GraphQLAPI(root_type=HelloAPI)
server = GraphQLMCP.from_api(api, name="Hello")
app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

Run it:

```bash
python server.py
```

Your MCP server is now running at `http://localhost:8002`.

## What Just Happened

1. **Defined a GraphQL API** — `@field` marks methods as GraphQL query fields
2. **Created an MCP server** — `GraphQLMCP.from_api()` analyzed the schema and generated MCP tools
3. **Started an HTTP server** — `http_app()` creates an ASGI app serving both MCP and GraphQL endpoints

## MCP Inspector

Visit `http://localhost:8002/graphql` in your browser to open the built-in MCP Inspector. It lets you:

- Browse all generated MCP tools
- Execute tools with custom parameters
- Add authentication headers
- View parameter and output schemas
- Track call history

The inspector runs alongside GraphiQL — both are available at `/graphql`. To disable it in production, set `graphql_http=False`.

## Pick Your Path

<div class="hero-grid">

<a class="hero-card" href="/python-libraries">
<h3>I use a Python GraphQL library</h3>
<p>Works alongside Strawberry, Ariadne, Graphene, graphql-api, or any graphql-core schema.</p>
</a>

<a class="hero-card" href="/existing-apis">
<h3>I have an existing GraphQL API</h3>
<p>Connect to any GraphQL API — GitHub, Shopify, Hasura, or your own, in any language.</p>
</a>

</div>

## Troubleshooting

### Server won't start

Make sure all dependencies are installed:

```bash
pip install graphql-mcp graphql-api uvicorn
```

### Tools not appearing

- Check that your GraphQL fields have docstrings (these become tool descriptions)
- Verify mutations are enabled: `allow_mutations=True`
- See [API Reference](/api-reference) for the complete tool generation rules

### Authentication errors

- Verify token format (include "Bearer " prefix if required)
- Check token hasn't expired
- Ensure auth configuration matches your API

### Type errors in tool calls

- Check parameter types match the schema
- Use proper JSON format for complex types
- Review the MCP Inspector schema panel for expected types
