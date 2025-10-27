---
title: Examples
weight: 5
---

# Examples

Practical examples demonstrating various GraphQL MCP use cases.

## Basic Hello World

A simple MCP server with a greeting function:

```python
import uvicorn
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

class GreetingAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"

api = GraphQLAPI(root_type=GreetingAPI)
server = GraphQLMCP.from_api(api, name="Greeting Service")
app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Book Store API

A more complex example with queries and mutations:

```python
import uvicorn
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP
from typing import Optional

class BookAPI:
    def __init__(self):
        self.books = [
            {"id": "1", "title": "The Hobbit", "author": "J.R.R. Tolkien"},
            {"id": "2", "title": "1984", "author": "George Orwell"}
        ]

    @field
    def book(self, id: str) -> Optional[dict]:
        """Get a book by ID."""
        return next((book for book in self.books if book["id"] == id), None)

    @field
    def books(self) -> list[dict]:
        """Get all books."""
        return self.books

    @field
    def add_book(self, title: str, author: str) -> dict:
        """Add a new book."""
        book = {
            "id": str(len(self.books) + 1),
            "title": title,
            "author": author
        }
        self.books.append(book)
        return book

    @field
    def update_book(self, id: str, title: Optional[str] = None,
                    author: Optional[str] = None) -> Optional[dict]:
        """Update a book's details."""
        book = next((b for b in self.books if b["id"] == id), None)
        if book:
            if title:
                book["title"] = title
            if author:
                book["author"] = author
        return book

api = GraphQLAPI(root_type=BookAPI())
server = GraphQLMCP.from_api(
    api,
    name="BookStore API",
    allow_mutations=True,
    graphql_http=True
)

app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Remote API - GitHub

Connect to GitHub's GraphQL API:

```python
import os
import uvicorn
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token=os.environ["GITHUB_TOKEN"],
    name="GitHub API",
    allow_mutations=True,
    graphql_http=True
)

app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

Usage:
```bash
export GITHUB_TOKEN=ghp_your_token_here
python github_api.py
```

## Remote API - Countries

Connect to a public GraphQL API:

```python
import uvicorn
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url="https://countries.trevorblades.com/",
    name="Countries API",
    graphql_http=True
)

app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Using with Strawberry

Integration with Strawberry GraphQL:

```python
import uvicorn
import strawberry
from graphql_mcp.server import GraphQLMCP

@strawberry.type
class Book:
    title: str
    author: str

@strawberry.type
class Query:
    @strawberry.field
    def books(self) -> list[Book]:
        return [
            Book(title="The Hobbit", author="J.R.R. Tolkien"),
            Book(title="1984", author="George Orwell")
        ]

    @strawberry.field
    def book(self, title: str) -> Book | None:
        books = self.books()
        return next((b for b in books if b.title == title), None)

schema = strawberry.Schema(query=Query)
server = GraphQLMCP(schema=schema._schema, name="Strawberry Books")

app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Production Deployment

A production-ready example with full configuration:

```python
import os
import uvicorn
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP
from starlette.middleware.cors import CORSMiddleware

# Configuration
HOST = os.environ.get("MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("MCP_PORT", "8002"))
WORKERS = int(os.environ.get("MCP_WORKERS", "4"))

class ProductionAPI:
    @field
    def health(self) -> str:
        """Health check endpoint."""
        return "OK"

    @field
    def version(self) -> str:
        """Get API version."""
        return "1.0.0"

    # Your API methods here...

api = GraphQLAPI(root_type=ProductionAPI())
server = GraphQLMCP.from_api(
    api,
    name="Production API",
    graphql_http=True,
    allow_mutations=True
)

app = server.http_app(transport="streamable-http", stateless_http=True)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    uvicorn.run(
        app,
        host=HOST,
        port=PORT,
        workers=WORKERS,
        log_level="info",
        access_log=True
    )
```

## Docker Deployment

Dockerfile for containerized deployment:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8002

CMD ["python", "app.py"]
```

docker-compose.yml:

```yaml
version: '3.8'

services:
  mcp-server:
    build: .
    ports:
      - "8002:8002"
    environment:
      - MCP_HOST=0.0.0.0
      - MCP_PORT=8002
      - GRAPHQL_TOKEN=${GRAPHQL_TOKEN}
    restart: unless-stopped
```

## Next Steps

- Learn about [testing](testing/)
- Check out the [API reference](api-reference/)
- Explore [configuration options](configuration/)
