---
title: "Python GraphQL Libraries"
---

# Python GraphQL Libraries

GraphQL MCP works alongside your existing Python GraphQL library. You keep your library for schema definition and resolvers — graphql-mcp adds MCP tool generation on top.

Any library that produces a `graphql-core` schema is supported.

## Library Setup

::: code-group
```python [graphql-api]
from graphql_api import GraphQLAPI, field
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
server = GraphQLMCP.from_api(api, name="Hello")  # [!code highlight]
app = server.http_app()
```

```python [Strawberry]
import strawberry
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
server = GraphQLMCP(schema=schema._schema, name="Hello")  # [!code highlight]
app = server.http_app()
```

```python [Ariadne]
from ariadne import make_executable_schema, QueryType
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
server = GraphQLMCP(schema=schema, name="Hello")  # [!code highlight]
app = server.http_app()
```

```python [Graphene]
import graphene
from graphql_mcp import GraphQLMCP

class Query(graphene.ObjectType):
    hello = graphene.String(name=graphene.String(default_value="World"))

    def resolve_hello(self, info, name):
        return f"Hello, {name}!"

schema = graphene.Schema(query=Query)
server = GraphQLMCP(schema=schema.graphql_schema, name="Hello")  # [!code highlight]
app = server.http_app()
```
:::

::: tip graphql-api has the tightest integration
Use `GraphQLMCP.from_api(api)` instead of passing the schema directly. This enables automatic schema extraction, custom scalar support (UUID, DateTime, etc.), and the `mcp_hidden` directive.
:::

::: info Schema access for Strawberry and Graphene
Strawberry wraps the graphql-core schema — access it via `schema._schema`. Graphene wraps it via `schema.graphql_schema`. Ariadne's `make_executable_schema` returns a graphql-core schema directly.
:::

## Schema Design for MCP

How you structure your GraphQL schema directly affects the quality of generated MCP tools.

### Write Descriptive Docstrings

Field docstrings become MCP tool descriptions — the primary way AI agents understand what a tool does.

```python
class API:
    @field
    def search_users(self, query: str, limit: int = 10) -> list[User]:
        """Search for users by name or email. Returns up to `limit` results."""  # [!code highlight]
        ...
```

::: warning
Fields without docstrings produce tools with no description — AI agents won't know what the tool does.
:::

### Choose Good Field Names

GraphQL field names (camelCase) are converted to snake_case for MCP tool names:

| Field Name | Tool Name | Quality |
|---|---|---|
| `searchUsers` | `search_users` | Clear |
| `getUserById` | `get_user_by_id` | Clear |
| `q` | `q` | Ambiguous |
| `data1` | `data_1` | Meaningless |

### Prefer Flat Arguments

Simple scalar arguments produce cleaner MCP tool schemas than nested input objects:

```python
# Good: flat arguments — clear tool schema
class API:
    @field(mutable=True)
    def create_user(self, name: str, email: str, age: int = 0) -> User:
        """Create a new user."""
        ...
```

::: tip
Input objects are supported (they become Pydantic models), but flat arguments are easier for AI agents to understand. Use input objects when grouping genuinely helps (e.g. `AddressInput` with `street`, `city`, `zip`).
:::

### Mark Mutations with `mutable=True`

In graphql-api, `@field` creates a Query field by default. Use `@field(mutable=True)` for mutations:

```python
class API:
    @field
    def get_users(self) -> list[User]:
        """List all users."""  # ← Query → read tool
        ...

    @field(mutable=True)
    def delete_user(self, id: UUID) -> bool:
        """Delete a user by ID."""  # ← Mutation → write tool
        ...
```

### Nested Tools

Beyond top-level fields, graphql-mcp generates tools for nested field paths that have arguments. This is useful for relationship queries:

```python
class UserAPI:
    @field
    def user(self, id: str) -> User:
        """Get a user by ID."""
        ...

class User:
    @field
    def posts(self, limit: int = 10) -> list[Post]:
        """Get this user's posts."""
        ...
```

This generates both a `user` tool and a `user_posts` tool:

```text
user(id) → User
user_posts(user_id, limit) → [Post]
```

Parent field arguments are automatically prefixed (`user_id`) to avoid collisions with the child field's own arguments (`limit`).

### Shape Return Types for MCP

graphql-mcp auto-builds selection sets that include scalar fields up to 5 levels deep. Flatten your return types to ensure the AI agent gets the data it needs:

```python
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
