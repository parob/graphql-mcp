---
title: "How It Works"
weight: 2
---

# How It Works

GraphQL MCP analyzes your GraphQL schema and generates MCP tools automatically. This page explains exactly what happens under the hood.

## Tool Generation

### Top-Level Fields

Each top-level field in your schema becomes an MCP tool:

- **Query fields** → read tools
- **Mutation fields** → write tools (when `allow_mutations=True`)

If a query and mutation have the same name, the **query takes precedence** — mutations are registered first, then queries overwrite any collisions.

### Tool Naming

GraphQL field names (camelCase) are converted to snake_case for MCP tool names:

| GraphQL Field | MCP Tool Name |
|---|---|
| `getUser` | `get_user` |
| `addBook` | `add_book` |
| `searchByTitle` | `search_by_title` |
| `users` | `users` |

### Tool Descriptions

Tool descriptions come from your GraphQL field descriptions. With [graphql-api](https://graphql-api.parob.com/), these are your Python docstrings:

```python
class API:
    @field
    def search_users(self, query: str) -> list[User]:
        """Search for users by name or email."""  # ← becomes the tool description
        ...
```

Fields without descriptions produce tools with no description — which makes them harder for AI agents to use effectively.

## Nested Tools

Beyond top-level fields, graphql-mcp also generates tools for **nested field paths** that have arguments.

### When Nested Tools Are Created

A nested tool is created when:
1. The field is at depth ≥ 2 (not a direct child of Query/Mutation)
2. The field has at least one argument

### Example

Given this schema:

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

GraphQL MCP generates **three** tools:

| Tool | From |
|---|---|
| `user` | Top-level query `user(id)` |
| `posts` | Top-level query `posts(limit)` — if `posts` exists at root |
| `user_posts` | Nested path `user(id) { posts(limit) }` |

### Argument Naming in Nested Tools

For nested tools, arguments from parent fields are prefixed with the parent field name to avoid collisions. Leaf field arguments keep their plain names:

```
user_posts(user_id: str, limit: int = 10)
           ^^^^^^^^       ^^^^^
           prefixed        plain (leaf)
```

### Recursion Prevention

Nested tool generation tracks visited types to prevent infinite recursion from circular type references.

## Selection Sets

When a tool returns an object type, graphql-mcp automatically builds a selection set to determine which fields to request.

### Rules

1. **Only scalar fields** are selected (strings, ints, bools, enums, etc.)
2. **Nested objects** are traversed up to **5 levels deep**
3. If an object has no scalar fields at all, `__typename` is returned as a fallback

### Example

For a `User` type with fields `id`, `name`, `email`, `address { street, city }`, the auto-generated selection set would be:

```graphql
{ id, name, email, address { street, city } }
```

If you need more control over which fields are returned, consider flattening your return types. See [Schema Design](../schema-design/) for patterns.

## Type Mapping

GraphQL types are automatically mapped to Python types for MCP tool schemas.

### Scalar Types

| GraphQL | Python | MCP Schema |
|---|---|---|
| `String` | `str` | `{"type": "string"}` |
| `Int` | `int` | `{"type": "integer"}` |
| `Float` | `float` | `{"type": "number"}` |
| `Boolean` | `bool` | `{"type": "boolean"}` |
| `ID` | `str` | `{"type": "string"}` |

### Custom Scalars (graphql-api)

When [graphql-api](https://graphql-api.parob.com/) is installed, additional scalar types are available:

| GraphQL | Python |
|---|---|
| `UUID` | `uuid.UUID` |
| `DateTime` | `datetime` |
| `Date` | `date` |
| `JSON` | `dict` |
| `Bytes` | `bytes` |

### Nullability

| GraphQL | Python | MCP Behavior |
|---|---|---|
| `String!` (non-null) | `str` | Required parameter |
| `String` (nullable) | `Optional[str]` | Optional parameter |
| `[String!]!` | `list[str]` | Required list |

### Enums

Enum types are mapped to `Literal` types with **case-insensitive validation**:

```python
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
```

All of these inputs are accepted for the `HIGH` value:
- `"HIGH"` (enum name)
- `"high"` (enum value)
- `"High"` (mixed case)

On output, enum names are automatically converted back to their values before being returned to the MCP client.

**Integer enums** are also supported — both the integer value and its string representation are accepted (e.g. both `1` and `"1"`).

### Input Objects

GraphQL input object types are automatically converted to **Pydantic models** with proper field types, descriptions, and required/optional markers. This gives MCP clients a detailed schema for complex inputs:

```python
# GraphQL input type
input CreateUserInput {
    name: String!
    email: String!
    age: Int
}

# Becomes a Pydantic model with:
# - name: str (required)
# - email: str (required)
# - age: Optional[int] (optional)
```

### Output Objects

Return types are also converted to Pydantic models, providing structured response schemas to MCP clients.

## JSON Scalar Handling

When using the `JSON` scalar from graphql-api:

- **Input:** Python dicts are automatically converted to JSON strings for GraphQL execution
- **Output:** JSON string responses are parsed back to Python dicts

For non-InputObject dict arguments without graphql-api, dicts are JSON-serialized by default.

## Local vs Remote Execution

GraphQL MCP supports both local schema execution and remote API proxying. The behavior differs in important ways:

### Local Schemas

When using `GraphQLMCP(schema=...)` or `GraphQLMCP.from_api(api)`:

- Tools execute GraphQL operations directly via `graphql()` from graphql-core
- Bearer tokens are automatically available through FastMCP's Context object
- No network overhead

### Remote Schemas

When using `GraphQLMCP.from_remote_url(url)`:

- Tools forward GraphQL queries to the remote server via HTTP
- The remote schema is introspected once at startup to determine types
- **Null-to-empty-array transformation:** `null` values for array fields are automatically converted to `[]` to satisfy MCP output schema validation
- **Undefined variable cleanup:** variables not provided by the MCP client are removed from the query to avoid remote server validation errors
- Bearer tokens are **not** automatically forwarded — use `forward_bearer_token=True` if needed (see [Configuration](../configuration/#forward_bearer_token))

## Next Steps

- **[Schema Design](../schema-design/)** — How to structure your schema for optimal MCP tools
- **[Configuration](../configuration/)** — Server configuration options
- **[API Reference](../api-reference/)** — Complete API documentation
