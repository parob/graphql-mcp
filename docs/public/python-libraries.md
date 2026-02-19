---
title: "Python GraphQL Libraries"
---

# Python GraphQL Libraries

GraphQL MCP works alongside your existing Python GraphQL library. You keep your library for schema definition and resolvers — graphql-mcp adds MCP tool generation on top.

Any library that produces a `graphql-core` schema is supported.

## With graphql-api

[graphql-api](https://graphql-api.parob.com/) provides the tightest integration — use `from_api` for automatic schema extraction:

```python
from graphql_api import GraphQLAPI, field
import uvicorn
from graphql_mcp import GraphQLMCP

class HelloAPI:
    @field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"

    @field(mutable=True)
    def set_greeting(self, message: str) -> str:
        """Update the greeting message."""
        return message

api = GraphQLAPI(root_type=HelloAPI)
server = GraphQLMCP.from_api(api, name="Hello")

app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## With Strawberry

```python
import strawberry
import uvicorn
from graphql_mcp import GraphQLMCP

@strawberry.type
class Query:
    @strawberry.field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"

@strawberry.type
class Mutation:
    @strawberry.mutation
    def set_greeting(self, message: str) -> str:
        """Update the greeting message."""
        return message

schema = strawberry.Schema(query=Query, mutation=Mutation)
server = GraphQLMCP(schema=schema._schema, name="Hello")

app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

> **Note:** Strawberry wraps the graphql-core schema — access it via `schema._schema`.

## With Ariadne

```python
from ariadne import make_executable_schema, QueryType
import uvicorn
from graphql_mcp import GraphQLMCP

type_defs = """
    type Query {
        hello(name: String = "World"): String!
    }
"""

query = QueryType()

@query.field("hello")
def resolve_hello(_, info, name="World"):
    return f"Hello, {name}!"

schema = make_executable_schema(type_defs, query)
server = GraphQLMCP(schema=schema, name="Hello")

app = server.http_app()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8002)
```

## With Graphene

```python
import graphene
from graphql_mcp import GraphQLMCP

class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="World"))

    def resolve_hello(self, info, name):
        return f"Hello, {name}!"

schema = graphene.Schema(query=Query)
server = GraphQLMCP(schema=schema.graphql_schema, name="Hello")
```

> **Note:** Graphene wraps the graphql-core schema — access it via `schema.graphql_schema`.

## Schema Design for MCP

How you structure your GraphQL schema directly affects the quality of generated MCP tools. These patterns apply primarily to [graphql-api](https://graphql-api.parob.com/), but the principles (descriptive names, flat arguments, clear return types) apply to any library.

### Write Descriptive Docstrings

Field docstrings become MCP tool descriptions — the primary way AI agents understand what a tool does. Without a docstring, the tool has no description.

```python
# Good: clear description helps the AI agent
class API:
    @field
    def search_users(self, query: str, limit: int = 10) -> list[User]:
        """Search for users by name or email. Returns up to `limit` results."""
        ...

# Bad: no description — the agent only sees the tool name and parameters
class API:
    @field
    def search_users(self, query: str, limit: int = 10) -> list[User]:
        ...
```

### Choose Good Field Names

GraphQL field names (camelCase) are converted to snake_case for MCP tool names:

| Field Name | Tool Name | Quality |
|---|---|---|
| `searchUsers` | `search_users` | Clear |
| `getUserById` | `get_user_by_id` | Clear |
| `q` | `q` | Ambiguous |
| `data1` | `data_1` | Meaningless |

For nested tools, parent and child names are joined with underscores (`user_posts`), so keep parent field names short.

### Prefer Flat Arguments

Simple scalar arguments produce cleaner MCP tool schemas than nested input objects:

```python
# Good: flat arguments — clear tool schema
class API:
    @field(mutable=True)
    def create_user(self, name: str, email: str, age: int = 0) -> User:
        """Create a new user."""
        ...

# Works but more complex: input object adds nesting
class API:
    @field(mutable=True)
    def create_user(self, input: CreateUserInput) -> User:
        """Create a new user."""
        ...
```

Input objects are automatically converted to Pydantic models with proper types, so they work. Use them when grouping genuinely helps (e.g. `AddressInput` with `street`, `city`, `zip`).

### Mark Mutations with `mutable=True`

In graphql-api, `@field` creates a Query field by default. Use `@field(mutable=True)` for mutations:

```python
class API:
    @field
    def get_users(self) -> list[User]:
        """List all users."""  # ← Query tool
        ...

    @field(mutable=True)
    def delete_user(self, id: UUID) -> bool:
        """Delete a user by ID."""  # ← Mutation tool
        ...
```

Only mutation tools are affected by `allow_mutations=False`.

### Shape Return Types for MCP

graphql-mcp auto-builds selection sets that include scalar fields up to 5 levels deep. If the AI agent needs specific data, put it at a reasonable depth or flatten your return type:

```python
# Good: important fields at top level
@dataclass
class UserSummary:
    id: UUID
    name: str
    email: str
    post_count: int      # Flattened — instead of user.posts.count
    last_login: datetime

class API:
    @field
    def get_user(self, id: UUID) -> UserSummary:
        """Get a user summary."""
        ...
```

See [API Reference](/api-reference#selection-sets) for details on selection set generation.

See also: [Existing APIs](/existing-apis) for connecting to remote GraphQL endpoints, [Configuration](/configuration) for mcp_hidden, auth, and middleware, [API Reference](/api-reference) for type mapping and tool generation details.
