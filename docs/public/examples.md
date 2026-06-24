---
title: "Examples"
---

# Examples

Runnable examples ship in the [`examples/`](https://github.com/parob/graphql-mcp/tree/main/examples) directory, each also deployed live at [examples.graphql-mcp.com](https://examples.graphql-mcp.com). The first four cover common use cases; a further five — under [GraphQL Library Examples](#graphql-library-examples) — demonstrate the same API across each popular GraphQL library.

## Hello World

Minimal MCP server with a single query — the simplest possible starting point.

[Source](https://github.com/parob/graphql-mcp/tree/main/examples/hello_world.py) · [Live demo](https://examples.graphql-mcp.com/hello-world/)

```python
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP


class HelloWorldAPI:

    @field
    def hello(self, name: str = "World") -> str:
        """Say hello to someone."""
        return f"Hello, {name}!"


api = GraphQLAPI(root_type=HelloWorldAPI)
server = GraphQLMCP.from_api(api)
app = server.http_app(transport="streamable-http", stateless_http=True)
```

## Task Manager

Full CRUD with enums, mutations, UUID/datetime scalars, and in-memory state.

[Source](https://github.com/parob/graphql-mcp/tree/main/examples/task_manager.py) · [Live demo](https://examples.graphql-mcp.com/task-manager/)

Demonstrates:
- Dataclass types as GraphQL object types
- Enums (`Priority`, `Status`)
- Queries with optional filters
- Mutations via `@field(mutable=True)`
- UUID and datetime scalars

```python
class TaskManagerAPI:

    @field
    def tasks(
        self,
        status: Optional[Status] = None,
        priority: Optional[Priority] = None,
    ) -> list[Task]:
        """List all tasks, optionally filtered by status or priority."""
        result = list(_tasks.values())
        if status is not None:
            result = [t for t in result if t.status == status]
        if priority is not None:
            result = [t for t in result if t.priority == priority]
        return result

    @field(mutable=True)
    def create_task(
        self,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        tags: Optional[list[str]] = None,
    ) -> Task:
        """Create a new task."""
        ...

    @field(mutable=True)
    def update_status(self, id: UUID, status: Status) -> Task:
        """Update a task's status. Automatically sets completed_at when done."""
        ...

    @field(mutable=True)
    def delete_task(self, id: UUID) -> bool:
        """Delete a task by ID. Returns true if the task existed."""
        ...
```

## Nested API

Nested tools, `@mcp` directive, Pydantic models, and async resolvers.

[Source](https://github.com/parob/graphql-mcp/tree/main/examples/nested_api.py) · [Live demo](https://examples.graphql-mcp.com/nested-api/)

Demonstrates:
- Nested query paths that auto-generate MCP tools (`category` → `category_articles`)
- `@mcp(hidden=True)` to hide arguments from MCP tools
- Pydantic `BaseModel` types as GraphQL object types
- Async resolvers
- Separate `query_type` / `mutation_type` pattern

```python
class Category:
    """A category containing articles."""

    @field
    async def articles(
        self,
        tag: Optional[str] = None,
        internal_score: Annotated[Optional[int], mcp(hidden=True)] = None,
    ) -> list[Article]:
        """List articles in this category, optionally filtered by tag.

        The internal_score argument is hidden from MCP tools via
        @mcp(hidden: true) but remains accessible through the GraphQL
        API directly.
        """
        ...
```

The `internal_score` parameter is visible in GraphiQL but hidden from MCP tools — useful for internal debugging arguments that AI agents shouldn't use.

The `Annotated[..., mcp(hidden=True)]` syntax shown here is graphql-api-specific. Users of Ariadne or `graphql.build_schema` apply the same directive inline in their SDL — see [Configuration → @mcp directive](/configuration#mcp-directive) for the per-library form.

## Remote API

Wraps a public GraphQL API (Countries) as MCP tools via `from_remote_url()`. No Python schema needed.

[Source](https://github.com/parob/graphql-mcp/tree/main/examples/remote_api.py) · [Live demo](https://examples.graphql-mcp.com/remote-api/)

```python
from graphql_mcp.server import GraphQLMCP

server = GraphQLMCP.from_remote_url(
    "https://countries.trevorblades.com/graphql",
    allow_mutations=False,
)
app = server.http_app(transport="streamable-http", stateless_http=True)
```

That's the entire file. `from_remote_url()` introspects the remote schema and generates read-only MCP tools automatically.

## GraphQL Library Examples

The same small "users" API, exposed through each popular GraphQL library — and each one demonstrating the [`@mcp` directive](/configuration#mcp-directive) (renaming a tool, renaming and hiding an argument, hiding a field). They're handy as copy-paste starting points for your own library.

Every example exposes the same MCP surface:
- `list_users` — a normal tool
- `fetch_user` — `getUserById` renamed via `@mcp`, with its `userId` argument exposed as `id`
- a hidden `internal_metrics` field and a hidden `debugToken` argument

| Library | Source | Live demo |
|---------|--------|-----------|
| **graphql-api** | [source](https://github.com/parob/graphql-mcp/tree/main/examples/library_graphql_api.py) | [demo](https://examples.graphql-mcp.com/library-graphql-api/) |
| **graphql-core** | [source](https://github.com/parob/graphql-mcp/tree/main/examples/library_graphql_core.py) | [demo](https://examples.graphql-mcp.com/library-graphql-core/) |
| **Ariadne** | [source](https://github.com/parob/graphql-mcp/tree/main/examples/library_ariadne.py) | [demo](https://examples.graphql-mcp.com/library-ariadne/) |
| **Strawberry** | [source](https://github.com/parob/graphql-mcp/tree/main/examples/library_strawberry.py) | [demo](https://examples.graphql-mcp.com/library-strawberry/) |
| **Graphene** | [source](https://github.com/parob/graphql-mcp/tree/main/examples/library_graphene.py) | [demo](https://examples.graphql-mcp.com/library-graphene/) |

Strawberry and Graphene apply `@mcp` a little differently from the SDL-based libraries — see [Strawberry & Graphene](/strawberry-graphene) if you need the specifics.

## Running Locally

```bash
cd examples
uv sync
uv run python hello_world.py   # or task_manager.py, nested_api.py, remote_api.py,
                               # or any of the library_*.py examples
```

Then open `http://localhost:8002/graphql` (port varies per example) to see GraphiQL and the MCP Inspector.
