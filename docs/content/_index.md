---
title: "GraphQL MCP for Python"
type: docs
---

> **Instantly expose any GraphQL API as MCP tools for AI agents and LLMs.**

# GraphQL MCP for Python

[![PyPI version](https://badge.fury.io/py/graphql-mcp.svg)](https://badge.fury.io/py/graphql-mcp)
[![Python versions](https://img.shields.io/pypi/pyversions/graphql-mcp.svg)](https://pypi.org/project/graphql-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is GraphQL MCP?

GraphQL MCP bridges the gap between GraphQL APIs and the Model Context Protocol (MCP), enabling AI agents to seamlessly interact with your GraphQL services.

**Works with ANY Python GraphQL library**: Strawberry, Ariadne, Graphene, graphql-api, or any library using graphql-core. If you already have a GraphQL API, you can expose it as MCP tools in minutes.

## Why GraphQL MCP?

| Feature | Description |
|---------|-------------|
| 🔄 **Automatic Tool Generation** | Converts GraphQL queries and mutations into MCP tools automatically. |
| 🛡️ **Type-Safe** | Maps GraphQL types to Python types with full type hints and validation. |
| 🌐 **Remote GraphQL Support** | Connect to existing GraphQL APIs with built-in authentication. |
| 🚀 **Production Ready** | Built on FastMCP and Starlette for high-performance async serving. |
| 🔍 **MCP Inspector** | Built-in web-based interface for testing and debugging MCP tools. |
| 🎨 **GraphiQL Integration** | Interactive GraphQL IDE combined with MCP tooling. |

## Quick Start

Install GraphQL MCP:

```bash
pip install graphql-mcp
```

**Already have a GraphQL API?** Expose it as MCP tools:

```python
import strawberry  # or any GraphQL library
from graphql_mcp.server import GraphQLMCP
import uvicorn

@strawberry.type
class Query:
    @strawberry.field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

schema = strawberry.Schema(query=Query)

# Expose as MCP tools - works with ANY graphql-core schema
server = GraphQLMCP(schema=schema._schema, name="My API")
app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

Works with Strawberry, Ariadne, Graphene, [graphql-api](https://graphql-api.parob.com/), or any library that produces a `graphql-core` schema.

## How It Works

GraphQL MCP analyzes your GraphQL schema and automatically:

1. **Discovers Operations** - Identifies all queries and mutations in your schema
2. **Generates Tools** - Creates corresponding MCP tools with proper type mappings
3. **Converts Names** - Transforms GraphQL naming to Python conventions (e.g., `addBook` → `add_book`)
4. **Preserves Docs** - Maintains all documentation and type information from your schema
5. **Enables Execution** - Provides HTTP endpoints for both MCP and GraphQL protocols

## Use Cases

### With Strawberry

Using [Strawberry](https://strawberry.rocks/) for your GraphQL API? Instant MCP integration:

```python
import strawberry
from graphql_mcp.server import GraphQLMCP

@strawberry.type
class Query:
    @strawberry.field
    def search_books(self, query: str) -> list[str]:
        """Search for books by title or author."""
        return ["The Hobbit", "1984"]

schema = strawberry.Schema(query=Query)
server = GraphQLMCP(schema=schema._schema, name="BookStore")
```

### With Ariadne

[Ariadne](https://ariadnegraphql.org/) user? Same simple approach:

```python
from ariadne import make_executable_schema, QueryType
from graphql_mcp.server import GraphQLMCP

type_defs = """
    type Query {
        searchBooks(query: String!): [String!]!
    }
"""

query = QueryType()

@query.field("searchBooks")
def resolve_search_books(_, info, query):
    return ["The Hobbit", "1984"]

schema = make_executable_schema(type_defs, query)
server = GraphQLMCP(schema=schema, name="BookStore")
```

### With graphql-api (Recommended for New Projects)

For new projects, [graphql-api](https://graphql-api.parob.com/) offers a clean decorator-based approach:

```python
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

class BookAPI:
    @field
    def search_books(self, query: str) -> list[str]:
        """Search for books by title or author."""
        return ["The Hobbit", "1984"]

api = GraphQLAPI(root_type=BookAPI)
server = GraphQLMCP.from_api(api, name="BookStore")
```

### With Remote GraphQL APIs

Connect to existing GraphQL endpoints and expose them as MCP tools:

```python
from graphql_mcp.server import GraphQLMCP

# Public API
server = GraphQLMCP.from_remote_url(
    url="https://countries.trevorblades.com/",
    name="Countries API"
)

# Authenticated API
github_server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="your_github_token",
    name="GitHub API"
)
```

### With Graphene

[Graphene](https://graphene-python.org/) works seamlessly:

```python
import graphene
from graphql_mcp.server import GraphQLMCP

class Query(graphene.ObjectType):
    search_books = graphene.List(graphene.String, query=graphene.String(required=True))

    def resolve_search_books(self, info, query):
        return ["The Hobbit", "1984"]

schema = graphene.Schema(query=Query)
server = GraphQLMCP(schema=schema.graphql_schema, name="BookStore")
```

### With Any GraphQL Library

GraphQL MCP works with **any** Python GraphQL library that produces a `graphql-core` schema. Simply pass the schema to GraphQLMCP:

```python
from graphql_mcp.server import GraphQLMCP

# Your schema from any library
server = GraphQLMCP(schema=your_graphql_schema, name="My API")
```

## MCP Inspector

GraphQL MCP includes a built-in web interface for testing and debugging your MCP tools. The inspector provides:

- 🔍 **Tool Discovery** - Browse all available MCP tools
- 🧪 **Interactive Testing** - Execute tools with custom parameters
- 🔐 **Authentication** - Test with Bearer tokens, API keys, or custom headers
- 📊 **Call History** - Track and review previous executions
- 📄 **Schema Inspection** - View detailed parameter and output schemas

Simply enable the GraphQL HTTP endpoint and access the inspector in your browser:

```python
server = GraphQLMCP.from_api(
    api,
    graphql_http=True,  # Enables GraphQL endpoint with MCP Inspector
)
```

## What's Next?

- 📚 **[Getting Started](docs/getting-started/)** - Learn the basics with our comprehensive guide
- 🔧 **[Configuration](docs/configuration/)** - Explore all configuration options
- 💡 **[Examples](docs/examples/)** - Practical examples for real-world scenarios
- 🔍 **[MCP Inspector](docs/mcp-inspector/)** - Learn about the testing interface
- 📖 **[API Reference](docs/api-reference/)** - Complete API documentation
