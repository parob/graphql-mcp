---
title: "Examples"
weight: 5
---

# Examples

Real-world examples of using GraphQL MCP with popular GraphQL libraries.

## Strawberry Example

A complete server using [Strawberry](https://strawberry.rocks/):

```python
import strawberry
import uvicorn
from graphql_mcp.server import GraphQLMCP

# In-memory data store
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

# Create MCP server
server = GraphQLMCP(
    schema=schema._schema,
    name="BookStore",
    graphql_http=True,  # Enable GraphiQL for testing
    allow_mutations=True
)

app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## Ariadne Example

Using [Ariadne](https://ariadnegraphql.org/) schema-first approach:

```python
from ariadne import make_executable_schema, QueryType, MutationType
import uvicorn
from graphql_mcp.server import GraphQLMCP

# Define schema
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

# In-memory data
books_data = [
    {"id": "1", "title": "The Hobbit", "author": "J.R.R. Tolkien"},
    {"id": "2", "title": "1984", "author": "George Orwell"}
]

# Define resolvers
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

# Create schema
schema = make_executable_schema(type_defs, query, mutation)

# Create MCP server
server = GraphQLMCP(
    schema=schema,
    name="BookStore",
    graphql_http=True
)

app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

## graphql-api Example

For new projects, [graphql-api](https://graphql-api.parob.com/) offers a decorator-based approach:

```python
import os
import uvicorn
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP
from graphql_mcp.auth import JWTVerifier

# Define your API
class BookStoreAPI:
    books = [
        {"id": "1", "title": "The Hobbit", "author": "J.R.R. Tolkien"},
        {"id": "2", "title": "1984", "author": "George Orwell"}
    ]

    @field
    def books(self) -> list[dict]:
        """Get all books in the store."""
        return self.books

    @field
    def book(self, id: str) -> dict | None:
        """Get a specific book by ID."""
        return next((b for b in self.books if b["id"] == id), None)

    @field
    def search_books(self, query: str) -> list[dict]:
        """Search books by title or author."""
        query_lower = query.lower()
        return [
            b for b in self.books
            if query_lower in b["title"].lower() or
               query_lower in b["author"].lower()
        ]

    @field
    def add_book(self, title: str, author: str) -> dict:
        """Add a new book to the store."""
        book = {
            "id": str(len(self.books) + 1),
            "title": title,
            "author": author
        }
        self.books.append(book)
        return book

# Create GraphQL API
api = GraphQLAPI(root_type=BookStoreAPI)

# Configure authentication (optional)
auth = None
if os.getenv("ENABLE_AUTH"):
    auth = JWTVerifier(
        jwks_uri=os.getenv("JWKS_URI"),
        issuer=os.getenv("JWT_ISSUER"),
        audience=os.getenv("JWT_AUDIENCE")
    )

# Create MCP server
server = GraphQLMCP.from_api(
    api,
    name="BookStore",
    graphql_http=os.getenv("ENABLE_GRAPHIQL", "true").lower() == "true",
    allow_mutations=True,
    auth=auth
)

# Create HTTP app
app = server.http_app(
    transport="streamable-http",
    stateless_http=True
)

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info")
    )
```

Run with:

```bash
PORT=8000 ENABLE_GRAPHIQL=true python bookstore_server.py
```

## Remote API Example

Connect to GitHub's GraphQL API:

```python
import os
import uvicorn
from graphql_mcp.server import GraphQLMCP

# Create server from GitHub's GraphQL API
server = GraphQLMCP.from_remote_url(
    url="https://api.github.com/graphql",
    bearer_token=os.getenv("GITHUB_TOKEN"),
    name="GitHub API"
)

# Enable inspector for testing
app = server.http_app()

if __name__ == "__main__":
    if not os.getenv("GITHUB_TOKEN"):
        print("Error: GITHUB_TOKEN environment variable required")
        print("Get one at: https://github.com/settings/tokens")
        exit(1)

    uvicorn.run(app, host="localhost", port=8000)
```

Run with:

```bash
GITHUB_TOKEN=ghp_your_token python github_server.py
```

## Multi-API Server

Serve multiple GraphQL APIs as different MCP servers:

```python
from starlette.applications import Starlette
from starlette.routing import Mount
from graphql_mcp.server import GraphQLMCP

# Create multiple servers
books_server = GraphQLMCP.from_api(books_api, name="Books")
users_server = GraphQLMCP.from_api(users_api, name="Users")

# Mount at different paths
app = Starlette(routes=[
    Mount("/mcp/books", app=books_server.http_app()),
    Mount("/mcp/users", app=users_server.http_app()),
])
```

## Testing Example

Test your MCP server:

```python
import pytest
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

class TestAPI:
    @field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

@pytest.fixture
def mcp_server():
    api = GraphQLAPI(root_type=TestAPI)
    return GraphQLMCP.from_api(api, name="Test")

def test_server_creation(mcp_server):
    assert mcp_server.name == "Test"
    assert mcp_server.schema is not None

def test_tool_generation(mcp_server):
    # Tools are generated from the schema
    app = mcp_server.http_app()
    # Test that the app is created successfully
    assert app is not None
```

## Docker Example

Dockerfile for deploying GraphQL MCP:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose port
EXPOSE 8000

# Run server
CMD ["python", "server.py"]
```

requirements.txt:

```txt
graphql-mcp
graphql-api
uvicorn
```

Build and run:

```bash
docker build -t graphql-mcp-server .
docker run -p 8000:8000 \
  -e GRAPHQL_URL=https://api.example.com/graphql \
  -e GRAPHQL_TOKEN=your_token \
  graphql-mcp-server
```

## Kubernetes Deployment

Deploy to Kubernetes:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: graphql-mcp
spec:
  replicas: 3
  selector:
    matchLabels:
      app: graphql-mcp
  template:
    metadata:
      labels:
        app: graphql-mcp
    spec:
      containers:
      - name: graphql-mcp
        image: your-registry/graphql-mcp:latest
        ports:
        - containerPort: 8000
        env:
        - name: PORT
          value: "8000"
        - name: GRAPHQL_URL
          valueFrom:
            secretKeyRef:
              name: graphql-secrets
              key: url
        - name: GRAPHQL_TOKEN
          valueFrom:
            secretKeyRef:
              name: graphql-secrets
              key: token
---
apiVersion: v1
kind: Service
metadata:
  name: graphql-mcp
spec:
  selector:
    app: graphql-mcp
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
```

## Serverless Example (AWS Lambda)

Deploy to AWS Lambda:

```python
from mangum import Mangum
from graphql_mcp.server import GraphQLMCP

# Create server
server = GraphQLMCP.from_api(api, name="Lambda API")

# Create HTTP app
app = server.http_app(stateless_http=True)

# Wrap for Lambda
handler = Mangum(app)
```

## Next Steps

- **[Configuration](configuration/)** - Customize these examples
- **[API Reference](api-reference/)** - Learn about all available options
- **[MCP Inspector](mcp-inspector/)** - Test your implementations
