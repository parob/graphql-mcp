---
title: "Examples"
---

# Examples

Complete runnable examples with popular GraphQL libraries.

## Strawberry

A bookstore server using [Strawberry](https://strawberry.rocks/):

```python
import strawberry
import uvicorn
from graphql_mcp import GraphQLMCP

books_data = [
    {"id": "1", "title": "The Hobbit", "author": "J.R.R. Tolkien"},
    {"id": "2", "title": "1984", "author": "George Orwell"}
]

@strawberry.type
class Book:
    id: str
    title: str
    author: str

@strawberry.type
class Query:
    @strawberry.field
    def books(self) -> list[Book]:
        """Get all books in the store."""
        return [Book(**b) for b in books_data]

    @strawberry.field
    def book(self, id: str) -> Book | None:
        """Get a specific book by ID."""
        book = next((b for b in books_data if b["id"] == id), None)
        return Book(**book) if book else None

@strawberry.type
class Mutation:
    @strawberry.mutation
    def add_book(self, title: str, author: str) -> Book:
        """Add a new book to the store."""
        book = {"id": str(len(books_data) + 1), "title": title, "author": author}
        books_data.append(book)
        return Book(**book)

schema = strawberry.Schema(query=Query, mutation=Mutation)
server = GraphQLMCP(schema=schema._schema, name="BookStore")

app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Ariadne

Using [Ariadne](https://ariadnegraphql.org/) schema-first approach:

```python
from ariadne import make_executable_schema, QueryType, MutationType
import uvicorn
from graphql_mcp import GraphQLMCP

type_defs = """
    type Book {
        id: ID!
        title: String!
        author: String!
    }

    type Query {
        books: [Book!]!
        book(id: ID!): Book
    }

    type Mutation {
        addBook(title: String!, author: String!): Book!
    }
"""

books_data = [
    {"id": "1", "title": "The Hobbit", "author": "J.R.R. Tolkien"},
    {"id": "2", "title": "1984", "author": "George Orwell"}
]

query = QueryType()
mutation = MutationType()

@query.field("books")
def resolve_books(_, info):
    return books_data

@query.field("book")
def resolve_book(_, info, id):
    return next((b for b in books_data if b["id"] == id), None)

@mutation.field("addBook")
def resolve_add_book(_, info, title, author):
    book = {"id": str(len(books_data) + 1), "title": title, "author": author}
    books_data.append(book)
    return book

schema = make_executable_schema(type_defs, query, mutation)
server = GraphQLMCP(schema=schema, name="BookStore")

app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## graphql-api

Using [graphql-api](https://graphql-api.parob.com/) with authentication:

```python
import os
import uvicorn
from graphql_api import GraphQLAPI, field
from graphql_mcp import GraphQLMCP
from fastmcp.server.auth.providers.jwt import JWTVerifier

class BookStoreAPI:
    @field
    def books(self) -> list[dict]:
        """Get all books in the store."""
        return [
            {"id": "1", "title": "The Hobbit", "author": "J.R.R. Tolkien"},
            {"id": "2", "title": "1984", "author": "George Orwell"}
        ]

    @field
    def search_books(self, query: str) -> list[dict]:
        """Search books by title or author."""
        return []

api = GraphQLAPI(root_type=BookStoreAPI)

auth = None
if os.getenv("ENABLE_AUTH"):
    auth = JWTVerifier(
        jwks_uri=os.getenv("JWKS_URI"),
        issuer=os.getenv("JWT_ISSUER"),
        audience=os.getenv("JWT_AUDIENCE")
    )

server = GraphQLMCP.from_api(api, name="BookStore", auth=auth)
app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## Remote API (GitHub)

Connect to GitHub's GraphQL API:

```python
import os
import uvicorn
from graphql_mcp import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token=os.getenv("GITHUB_TOKEN"),
    name="GitHub API"
)

app = server.http_app()

if __name__ == "__main__":
    if not os.getenv("GITHUB_TOKEN"):
        print("Error: GITHUB_TOKEN environment variable required")
        print("Get one at: https://github.com/settings/tokens")
        exit(1)
    uvicorn.run(app, host="localhost", port=8002)
```

## Multi-API Server

Serve multiple GraphQL APIs as different MCP servers:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from graphql_mcp import GraphQLMCP

books_server = GraphQLMCP.from_api(books_api, name="Books")
users_server = GraphQLMCP.from_api(users_api, name="Users")

app = Starlette(routes=[
    Mount("/mcp/books", app=books_server.http_app()),
    Mount("/mcp/users", app=users_server.http_app()),
])
```

## Testing

```python
import pytest
from graphql_api import GraphQLAPI, field
from graphql_mcp import GraphQLMCP

class TestAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Say hello."""
        return f"Hello, {name}!"

@pytest.fixture
def mcp_server():
    api = GraphQLAPI(root_type=TestAPI)
    return GraphQLMCP.from_api(api, name="Test")

def test_server_creation(mcp_server):
    assert mcp_server.name == "Test"
    assert mcp_server.schema is not None

def test_tool_generation(mcp_server):
    app = mcp_server.http_app()
    assert app is not None
```

## Next Steps

- **[Deployment](/deployment)** — Docker, Kubernetes, serverless
- **[Customization](/customization)** — Auth, mcp_hidden, middleware
- **[API Reference](/api-reference)** — Full parameter reference
