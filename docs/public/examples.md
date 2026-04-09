---
title: "Examples"
---

# Examples

Four runnable examples ship in the [`examples/`](https://github.com/parob/graphql-mcp/tree/main/examples) directory. Each one is also deployed live at [examples.graphql-mcp.com](https://examples.graphql-mcp.com).

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

Nested tools, `@mcpHidden` directive, Pydantic models, and async resolvers.

[Source](https://github.com/parob/graphql-mcp/tree/main/examples/nested_api.py) · [Live demo](https://examples.graphql-mcp.com/nested-api/)

Demonstrates:
- Nested query paths that auto-generate MCP tools (`category` → `category_articles`)
- `@mcpHidden` directive to hide arguments from MCP tools
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
        internal_score: Annotated[Optional[int], mcp_hidden] = None,
    ) -> list[Article]:
        """List articles in this category, optionally filtered by tag.

        The internal_score argument is hidden from MCP tools via @mcpHidden
        but remains accessible through the GraphQL API directly.
        """
        ...
```

The `internal_score` parameter is visible in GraphiQL but hidden from MCP tools — useful for internal debugging arguments that AI agents shouldn't use.

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

## Running Locally

```bash
cd examples
uv sync
uv run python hello_world.py   # or task_manager.py, nested_api.py, remote_api.py
```

Then open `http://localhost:8002/graphql` (port varies per example) to see GraphiQL and the MCP Inspector.
