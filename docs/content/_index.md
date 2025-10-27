---
title: "GraphQL MCP for Python"
type: docs
---

> **Automatically convert GraphQL APIs into MCP tools for AI agents with full type safety and authentication support.**

# GraphQL MCP for Python

[![PyPI version](https://badge.fury.io/py/graphql-mcp.svg)](https://badge.fury.io/py/graphql-mcp)
[![Python versions](https://img.shields.io/pypi/pyversions/graphql-mcp.svg)](https://pypi.org/project/graphql-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Why GraphQL MCP?

`graphql-mcp` bridges the gap between GraphQL APIs and AI agents by automatically generating [Model Context Protocol (MCP)](https://modelcontextprotocol.io) tools from your GraphQL schema. This enables AI systems to seamlessly interact with your GraphQL APIs as structured tools with full type safety.

## Key Features

| Feature | Description |
|---------|-------------|
| 🤖 **Automatic Tool Generation** | Converts GraphQL queries and mutations into MCP tools automatically. |
| 🔒 **Type-Safe** | Maps GraphQL types to Python types with full type hints and validation. |
| 🌐 **Remote GraphQL Support** | Connect to existing GraphQL APIs from any provider. |
| 🔐 **Authentication Ready** | Built-in support for JWT and bearer token authentication. |
| 🎨 **MCP Inspector** | Web-based interface for testing and debugging MCP tools. |
| 🚀 **Production Ready** | Built on FastMCP and Starlette for excellent performance. |

## Quick Start

Get up and running in minutes:

```bash
pip install graphql-mcp graphql-api
```

```python
import uvicorn
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

# Define your GraphQL API
class HelloWorldAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Greet someone by name."""
        return f"Hello, {name}!"

# Create API and MCP server
api = GraphQLAPI(root_type=HelloWorldAPI)
server = GraphQLMCP.from_api(api)

# Serve as HTTP endpoint
app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Connect to Remote GraphQL APIs

You can also expose existing GraphQL APIs as MCP tools:

```python
from graphql_mcp.server import GraphQLMCP

# Connect to a public GraphQL API
server = GraphQLMCP.from_remote_url(
    url="https://countries.trevorblades.com/",
    name="Countries API"
)

# With authentication
authenticated_server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token="your_github_token",
    name="GitHub API"
)

# Serve as HTTP endpoint
app = server.http_app()
```

## Use with graphql-api

For building GraphQL schemas, we recommend **[graphql-api](https://github.com/parob/graphql-api)** - our companion package that provides a simple, decorator-based approach:

```python
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

class BookAPI:
    books = [
        {"id": "1", "title": "The Hobbit", "author": "J.R.R. Tolkien"},
        {"id": "2", "title": "1984", "author": "George Orwell"}
    ]

    @field
    def book(self, id: str) -> dict:
        """Get a book by ID."""
        return next((book for book in self.books if book["id"] == id), None)

    @field
    def add_book(self, title: str, author: str) -> dict:
        """Add a new book."""
        book = {"id": str(len(self.books) + 1), "title": title, "author": author}
        self.books.append(book)
        return book

api = GraphQLAPI(root_type=BookAPI)
server = GraphQLMCP.from_api(api, name="BookStore")
```

Learn more at [parob.github.io/graphql-api](https://parob.github.io/graphql-api).

## MCP Inspector

GraphQL MCP includes a built-in web-based inspector for testing and debugging your MCP tools:

![MCP Inspector Interface](mcp_inspector.png)

- **Tool Discovery**: Browse all available MCP tools from your schema
- **Interactive Testing**: Execute tools with custom parameters
- **Authentication Support**: Test with Bearer tokens and custom headers
- **Schema Inspection**: View detailed parameter and output schemas

## What's Next?

- 📚 **[Getting Started](docs/getting-started/)** - Learn the basics with our comprehensive guide
- 💡 **[Examples](docs/examples/)** - Explore practical examples and tutorials for real-world scenarios
- 📖 **[API Reference](docs/api-reference/)** - Check out the complete API documentation
