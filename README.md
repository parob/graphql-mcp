# GraphQL-MCP

[![PyPI version](https://badge.fury.io/py/graphql-mcp.svg)](https://badge.fury.io/py/graphql-mcp)
[![Python versions](https://img.shields.io/pypi/pyversions/graphql-mcp.svg)](https://pypi.org/project/graphql-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**[📚 Documentation](https://graphql-mcp.parob.com/)** | **[📦 PyPI](https://pypi.org/project/graphql-mcp/)** | **[🔧 GitHub](https://github.com/parob/graphql-mcp)**

---

A library for automatically generating [FastMCP](https://pypi.org/project/fastmcp/) tools from GraphQL APIs using [graphql-api](https://pypi.org/project/graphql-api/).

This allows you to expose your GraphQL API as MCP tools that can be used by AI agents and other systems.

## Quick Start

Install graphql-mcp with graphql-api:

```bash
pip install graphql-mcp graphql-api
```

Create a simple GraphQL API and expose it as MCP tools:

```python
import asyncio
import uvicorn

from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP


class HelloWorldAPI:

    @field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"


api = GraphQLAPI(root_type=HelloWorldAPI)

server = GraphQLMCP.from_api(api)

mcp_app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)


if __name__ == "__main__":
    uvicorn.run(mcp_app, host="0.0.0.0", port=8002)
```

That's it! Your GraphQL API is now available as MCP tools.

## Features

- **Automatic Tool Generation**: Converts GraphQL queries and mutations into MCP tools
- **Type-Safe**: Maps GraphQL types to Python types with full type hints
- **Built-in HTTP Server**: Serves both MCP and GraphQL endpoints
- **Authentication**: Supports JWT and bearer token authentication
- **Remote GraphQL**: Connect to existing GraphQL APIs
- **Production Ready**: Built on FastMCP and Starlette
- **Built-in MCP Inspector**: Web-based GraphiQL interface for testing and debugging

## Documentation

**Visit the [official documentation](https://graphql-mcp.parob.com/)** for comprehensive guides, examples, and API reference.

### Key Topics

- **[Getting Started](https://graphql-mcp.parob.com/docs/getting-started/)** - Quick introduction and basic usage
- **[Configuration](https://graphql-mcp.parob.com/docs/configuration/)** - Configure your MCP server
- **[Remote GraphQL](https://graphql-mcp.parob.com/docs/remote-graphql/)** - Connect to existing GraphQL APIs
- **[MCP Inspector](https://graphql-mcp.parob.com/docs/mcp-inspector/)** - Test and debug your tools
- **[Examples](https://graphql-mcp.parob.com/docs/examples/)** - Real-world usage examples
- **[API Reference](https://graphql-mcp.parob.com/docs/api-reference/)** - Complete API documentation

## Usage with graphql-api

The recommended way to use GraphQL MCP is with the [graphql-api](https://github.com/parob/graphql-api) library, which provides a simple, decorator-based approach to building GraphQL APIs:

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
    def books(self) -> list[dict]:
        """Get all books."""
        return self.books

    @field
    def add_book(self, title: str, author: str) -> dict:
        """Add a new book."""
        book = {"id": str(len(self.books) + 1), "title": title, "author": author}
        self.books.append(book)
        return book

api = GraphQLAPI(root_type=BookAPI)
server = GraphQLMCP.from_api(api, name="BookStore")
```

## Remote GraphQL APIs

You can also connect to existing GraphQL APIs:

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
```

## Other GraphQL Libraries

GraphQL MCP works with any GraphQL library that produces a `graphql-core` schema:

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

## Configuration

```python
server = GraphQLMCP.from_api(
    api,
    name="My API",
    graphql_http=True,          # Enable GraphQL HTTP endpoint
    allow_mutations=True,       # Allow mutation tools
    auth=jwt_verifier,         # Optional JWT authentication
)

# Serve with custom configuration
app = server.http_app(
    transport="streamable-http",  # or "http" or "sse"
    stateless_http=True,         # Don't maintain client state
)
```

## How It Works

1. **Schema Analysis**: GraphQL MCP analyzes your GraphQL schema
2. **Tool Generation**: Each query and mutation becomes an MCP tool
3. **Type Mapping**: GraphQL types are mapped to Python types
4. **Execution**: Tools execute GraphQL operations when called
5. **HTTP Serving**: Both MCP and GraphQL endpoints are served

The generated tools use `snake_case` naming (e.g., `addBook` becomes `add_book`) and preserve all type information and documentation from your GraphQL schema.

## MCP Inspector

GraphQL-MCP includes a built-in MCP Inspector that provides a web-based interface for testing and debugging your MCP tools. The inspector is automatically injected into GraphiQL interfaces when serving your GraphQL endpoints.

<img src="docs/mcp_inspector.png" alt="MCP Inspector Interface" width="600">

### Features

- **Tool Discovery**: Browse all available MCP tools generated from your GraphQL schema
- **Interactive Testing**: Execute tools with custom parameters and see real-time results
- **Authentication Support**: Test with Bearer tokens, API keys, or custom headers
- **Call History**: Track and review previous tool executions
- **Schema Inspection**: View detailed parameter and output schemas for each tool
- **Real-time Status**: Monitor connection status and tool availability

### Accessing the Inspector

When you enable GraphQL HTTP endpoints, the MCP Inspector is automatically available:

```python
server = GraphQLMCP.from_api(
    api,
    name="My API",
    graphql_http=True,  # This enables the GraphQL endpoint with MCP Inspector
)

app = server.http_app()
```

Navigate to your server in a web browser to access the inspector interface.

## License

MIT License - see [LICENSE](LICENSE) file for details.
