"""Task Manager - CRUD example with enums, mutations, and in-memory state.

Demonstrates:
- Dataclass types as GraphQL object types
- Enums (Priority, Status)
- Queries with optional filters
- Mutations via @field(mutable=True)
- UUID and datetime scalars
- Optional fields and list types
"""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP


class Priority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Status(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"


@dataclass
class Task:
    id: UUID
    title: str
    description: str
    status: Status
    priority: Priority
    tags: list[str]
    created_at: datetime
    completed_at: Optional[datetime] = None


# In-memory store, seeded with sample data
_tasks: dict[UUID, Task] = {}


def _seed():
    for title, desc, priority, status, tags in [
        ("Set up CI/CD", "Configure GitHub Actions pipeline",
         Priority.HIGH, Status.DONE, ["devops", "infrastructure"]),
        ("Write API docs", "Document all GraphQL endpoints",
         Priority.MEDIUM, Status.IN_PROGRESS, ["docs"]),
        ("Fix login bug", "Users getting 401 on valid credentials",
         Priority.CRITICAL, Status.TODO, ["bug", "auth"]),
        ("Add dark mode", "Support dark theme in web app",
         Priority.LOW, Status.TODO, ["frontend", "ui"]),
    ]:
        task = Task(
            id=uuid4(), title=title, description=desc,
            status=status, priority=priority, tags=tags,
            created_at=datetime(2026, 1, 15, 9, 0, 0),
            completed_at=datetime(2026, 2, 1, 14, 30, 0) if status == Status.DONE else None,
        )
        _tasks[task.id] = task


_seed()


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

    @field
    def task(self, id: UUID) -> Optional[Task]:
        """Get a single task by ID."""
        return _tasks.get(id)

    @field(mutable=True)
    def create_task(
        self,
        title: str,
        description: str = "",
        priority: Priority = Priority.MEDIUM,
        tags: Optional[list[str]] = None,
    ) -> Task:
        """Create a new task."""
        task = Task(
            id=uuid4(),
            title=title,
            description=description,
            status=Status.TODO,
            priority=priority,
            tags=tags or [],
            created_at=datetime.now(),
        )
        _tasks[task.id] = task
        return task

    @field(mutable=True)
    def update_status(self, id: UUID, status: Status) -> Task:
        """Update a task's status. Automatically sets completed_at when done."""
        task = _tasks[id]
        task.status = status
        if status == Status.DONE:
            task.completed_at = datetime.now()
        elif task.completed_at is not None:
            task.completed_at = None
        return task

    @field(mutable=True)
    def delete_task(self, id: UUID) -> bool:
        """Delete a task by ID. Returns true if the task existed."""
        if id in _tasks:
            del _tasks[id]
            return True
        return False


api = GraphQLAPI(root_type=TaskManagerAPI)
server = GraphQLMCP.from_api(api, allow_mutations=True, graphql_http_kwargs={
    "graphiql_example_query": """\
# List all tasks
{
  tasks {
    id
    title
    status
    priority
    tags
    createdAt
  }
}

# Filter by status
# {
#   tasks(status: TODO) {
#     title
#     priority
#   }
# }

# Create a task
# mutation {
#   createTask(
#     title: "My new task"
#     description: "Something important"
#     priority: HIGH
#     tags: ["example"]
#   ) {
#     id
#     title
#     createdAt
#   }
# }""",
})
app = server.http_app(transport="streamable-http", stateless_http=True)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
