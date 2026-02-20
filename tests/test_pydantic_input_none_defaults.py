"""
Test that Pydantic input objects with optional fields that have defaults
work correctly via MCP tool calls (the LLM omits optional fields).

Regression test for: when graphql-mcp serializes dynamic Pydantic models
using model_dump(mode="json"), unset optional fields were serialized as None,
overriding GraphQL schema defaults and causing ValidationError in the resolver.
"""

import json
import pytest
from enum import Enum
from typing import List
from pydantic import BaseModel
from fastmcp.client import Client

try:
    from graphql_api import GraphQLAPI
    HAS_GRAPHQL_API = True
except ImportError:
    HAS_GRAPHQL_API = False

from graphql_mcp.server import GraphQLMCP


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_list_pydantic_input_with_enum_default_omitted():
    """
    When an MCP client omits an optional field that has a non-None default
    (e.g., role: Role = Role.USER), the resolver should receive the Pydantic
    model with that default applied — not fail with a ValidationError.
    """
    class Priority(str, Enum):
        LOW = "low"
        MEDIUM = "medium"
        HIGH = "high"

    class Task(BaseModel):
        title: str
        priority: Priority = Priority.MEDIUM  # Default that differs from None

    class Result(BaseModel):
        count: int
        priorities: List[str]

    received = []

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def process_tasks(self, tasks: List[Task]) -> Result:
            """Process tasks."""
            priorities = []
            for task in tasks:
                assert isinstance(task, Task), f"Expected Task, got {type(task)}"
                assert hasattr(task, "priority"), "Task missing priority attr"
                received.append(task)
                priorities.append(task.priority.value)
            return Result(count=len(tasks), priorities=priorities)

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Call without providing 'priority' — should use default MEDIUM
        result = await client.call_tool("process_tasks", {
            "tasks": [
                {"title": "Task 1"},  # No priority — should default to MEDIUM
                {"title": "Task 2", "priority": "low"},  # Explicit priority
            ]
        })

        text = result.content[0].text if hasattr(result, 'content') else result[0].text
        data = json.loads(text)

        assert data["count"] == 2
        assert len(received) == 2
        assert received[0].priority == Priority.MEDIUM  # Default applied
        assert received[1].priority == Priority.LOW  # Explicit value kept


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_single_pydantic_input_with_none_default_field():
    """
    Same issue but with a single Pydantic model argument (not a list).
    """
    class Status(str, Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"

    class Config(BaseModel):
        name: str
        status: Status = Status.ACTIVE

    class ConfigResult(BaseModel):
        name: str
        status: str

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def update_config(self, config: Config) -> ConfigResult:
            """Update config."""
            assert isinstance(config, Config), f"Expected Config, got {type(config)}"
            return ConfigResult(name=config.name, status=config.status.value)

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Only provide 'name', omit 'status'
        result = await client.call_tool("update_config", {
            "config": {"name": "test"}
        })

        text = result.content[0].text if hasattr(result, 'content') else result[0].text
        data = json.loads(text)

        assert data["name"] == "test"
        assert data["status"] == "active"  # Default applied
