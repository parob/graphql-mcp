---
title: "Getting Started"
---

# Getting Started

GraphQL MCP exposes GraphQL APIs as MCP tools for AI agents. Works with any GraphQL library.

## Installation

```bash
pip install graphql-mcp
```

Or using uv (recommended):

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

Your MCP server is running on `http://localhost:8002`. Visit `http://localhost:8002/graphql` to test with the built-in MCP Inspector.

## What Just Happened?

1. **Defined a GraphQL API** — `@field` marks methods as GraphQL query fields
2. **Created MCP Server** — `GraphQLMCP.from_api()` analyzed the schema and generated MCP tools
3. **Started HTTP Server** — `http_app()` creates an ASGI app serving both MCP and GraphQL endpoints

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

<a class="hero-card" href="/how-it-works">
<h3>I want to understand the internals</h3>
<p>How tool generation works, type mapping, selection sets, nested tools.</p>
</a>

<a class="hero-card" href="/customization">
<h3>I want to customize behavior</h3>
<p>mcp_hidden, auth, mutations, middleware, and other configuration.</p>
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
- See [How It Works](/how-it-works) for the complete tool generation rules
