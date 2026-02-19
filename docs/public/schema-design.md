---
title: "Schema Design"
---

# Schema Design for MCP

How you structure your GraphQL schema directly affects the quality of the MCP tools graphql-mcp generates. This guide covers patterns specific to graphql-mcp and [graphql-api](https://graphql-api.parob.com/).

## Write Descriptive Docstrings

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

## Choose Good Field Names

GraphQL field names are converted from camelCase to snake_case for MCP tool names. Choose names that are self-explanatory:

| Field Name | Tool Name | Quality |
|---|---|---|
| `searchUsers` | `search_users` | Clear |
| `getUserById` | `get_user_by_id` | Clear |
| `q` | `q` | Ambiguous |
| `data1` | `data_1` | Meaningless |

For nested tools, parent and child names are joined with underscores (`user_posts`), so keep parent field names short to avoid unwieldy tool names like `organization_team_member_permissions`.

## Use `mcp_hidden` for Server-Side Arguments

Some arguments should be populated server-side (from auth context, request metadata, etc.) rather than by the AI agent. Use `mcp_hidden` to hide them from MCP while keeping them in the GraphQL schema:

```python
from typing import Annotated, Optional
from uuid import UUID
from graphql_api import GraphQLAPI, field
from graphql_mcp import mcp_hidden

class API:
    @field(mutable=True)
    def create_item(
        self,
        name: str,
        description: str = "",
        user_id: Annotated[Optional[UUID], mcp_hidden] = None,
    ) -> Item:
        """Create a new item."""
        # user_id is filled from auth context, not by the AI agent
        ...

api = GraphQLAPI(root_type=API, directives=[mcp_hidden])
```

The MCP tool exposes only `name` and `description`. The `user_id` argument still exists in the GraphQL schema for direct API consumers.

**Rules:**
- Hidden arguments **must** have a default value
- Register the directive: `GraphQLAPI(..., directives=[mcp_hidden])`
- Works with SDL too: `@mcpHidden` on argument definitions

## Design Enums for Readability

Enum values are validated case-insensitively — both the enum name and value are accepted. Design your enums so either form reads naturally:

```python
class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
```

An AI agent can send `"HIGH"`, `"high"`, or `"High"` — all work. Integer enums also accept both the number and its string form (e.g. `1` and `"1"`).

## Prefer Flat Arguments

Simple scalar arguments produce cleaner MCP tool schemas than nested input objects:

```python
# Good: flat arguments — clear tool schema
class API:
    @field(mutable=True)
    def create_user(self, name: str, email: str, age: int = 0) -> User:
        """Create a new user."""
        ...

# Works but more complex: input object adds nesting to the tool interface
class API:
    @field(mutable=True)
    def create_user(self, input: CreateUserInput) -> User:
        """Create a new user."""
        ...
```

Input objects are automatically converted to Pydantic models with proper types, so they do work. Use them when grouping genuinely helps (e.g. an `AddressInput` with `street`, `city`, `zip`).

## Mark Mutations with `mutable=True`

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

Only mutation tools are affected by `allow_mutations=False`. If you forget `mutable=True`, the field becomes a query and will always be exposed.

## Shape Return Types for MCP

graphql-mcp auto-builds selection sets that include scalar fields up to 5 levels deep. This means:

- **Scalar fields** (str, int, bool, enums) are always included
- **Nested object fields** are traversed automatically
- **Very deep nesting** (>5 levels) is truncated

If you need the AI agent to see specific data, put it at a reasonable depth or flatten your return type:

```python
# Good: important fields are at the top level
@dataclass
class UserSummary:
    id: UUID
    name: str
    email: str
    post_count: int      # Flattened — instead of requiring user.posts.count
    last_login: datetime

class API:
    @field
    def get_user(self, id: UUID) -> UserSummary:
        """Get a user summary."""
        ...
```

## Next Steps

- **[How It Works](/how-it-works)** — Detailed mechanics of tool generation
- **[Configuration](/configuration)** — Server configuration options
- **[Examples](/examples)** — Complete working examples
