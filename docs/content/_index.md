---
title: "GraphQL MCP for Python"
type: docs
---

> **A framework for automatically generating FastMCP tools from GraphQL APIs.**

# GraphQL MCP for Python

[![PyPI version](https://badge.fury.io/py/graphql-mcp.svg)](https://badge.fury.io/py/graphql-mcp)
[![Python versions](https://img.shields.io/pypi/pyversions/graphql-mcp.svg)](https://pypi.org/project/graphql-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## What is GraphQL MCP?

GraphQL MCP bridges the gap between GraphQL APIs and the Model Context Protocol (MCP), enabling AI agents to seamlessly interact with your GraphQL services. By automatically converting GraphQL queries and mutations into MCP tools, GraphQL MCP makes it effortless to expose your existing GraphQL infrastructure to AI systems.

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

Get up and running in minutes:

```bash
pip install graphql-mcp graphql-api
```

```python
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP
import uvicorn

class HelloWorldAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """A classic greeting."""
        return f"Hello, {name}!"

api = GraphQLAPI(root_type=HelloWorldAPI)
server = GraphQLMCP.from_api(api)

# Serve as MCP over HTTP
mcp_app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)

if __name__ == "__main__":
    uvicorn.run(mcp_app, host="0.0.0.0", port=8002)
```

## How It Works

GraphQL MCP analyzes your GraphQL schema and automatically:

1. **Discovers Operations** - Identifies all queries and mutations in your schema
2. **Generates Tools** - Creates corresponding MCP tools with proper type mappings
3. **Converts Names** - Transforms GraphQL naming to Python conventions (e.g., `addBook` → `add_book`)
4. **Preserves Docs** - Maintains all documentation and type information from your schema
5. **Enables Execution** - Provides HTTP endpoints for both MCP and GraphQL protocols

## Use Cases

### With graphql-api

Build new GraphQL APIs and automatically expose them as MCP tools using [graphql-api](https://graphql-api.parob.com/):

```python
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

class BookAPI:
    @field
    def search_books(self, query: str) -> list[dict]:
        """Search for books by title or author."""
        # Your search logic here
        return []

api = GraphQLAPI(root_type=BookAPI)
server = GraphQLMCP.from_api(api, name="BookStore")
```

> **Learn more**: See [graphql-api documentation](https://graphql-api.parob.com/) for building GraphQL APIs.

### With Database-Backed APIs

For database integration, use [graphql-db](https://graphql-db.parob.com/):

```python
from graphql_db.orm_base import DatabaseManager, ModelBase
from graphql_mcp.server import GraphQLMCP

# Database models automatically become GraphQL types
db_manager = DatabaseManager(url="sqlite:///myapp.db")
# ... define models and API ...

server = GraphQLMCP.from_api(api, name="Database API")
```

> **Learn more**: See [graphql-db documentation](https://graphql-db.parob.com/) for database integration.

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

### With Other GraphQL Libraries

Works with any Python GraphQL library that produces a `graphql-core` schema (Strawberry, Ariadne, etc.):

```python
import strawberry
from graphql_mcp.server import GraphQLMCP

@strawberry.type
class Query:
    @strawberry.field
    def greeting(self, name: str) -> str:
        return f"Hello, {name}!"

schema = strawberry.Schema(query=Query)
server = GraphQLMCP(schema=schema._schema, name="Strawberry API")
```

> **Recommendation**: We recommend [graphql-api](https://graphql-api.parob.com/) for the best experience with GraphQL MCP.

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
