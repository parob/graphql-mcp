"""
Test to reproduce and fix the enum value-to-name mapping issue.

This test reproduces the specific issue where:
- Enum has lowercase values: Role(str, Enum) with USER = "user", ASSISTANT = "assistant"
- Input data contains enum values: {"role": "user"}
- GraphQL expects enum names: "USER"
- Our processing should map "user" -> "USER"
"""
import json
import pytest
from pydantic import BaseModel
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast, List
import enum

from graphql_mcp.server import add_tools_from_schema


def get_result_text(result):
    """Helper function to get text from result, handling different FastMCP API versions"""
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    else:
        return cast(TextContent, result[0]).text


@pytest.mark.asyncio
async def test_enum_value_to_name_mapping_in_lists():
    """
    Test that reproduces the enum value-to-name mapping issue in list input objects.

    The issue: Input data has enum values ('user', 'assistant')
    but GraphQL expects enum names ('USER', 'ASSISTANT').
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    # Exact enum structure from user's code
    class Role(str, enum.Enum):
        """The role of a message."""
        USER = "user"
        SYSTEM = "system"
        ASSISTANT = "assistant"
        ASSISTANT_INTERNAL = "assistant_internal"
        ASSISTANT_FEEDBACK = "assistant_feedback"

    class Response(BaseModel):
        message: str
        role: Role = Role.USER

    class ResponseStatus(BaseModel):
        success: bool
        count: int
        processed_roles: List[str]

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def send_responses(self, responses: List[Response]) -> ResponseStatus:
            """Send responses - this should handle enum value-to-name conversion correctly."""
            processed_roles = []
            for response in responses:
                if hasattr(response, 'role'):
                    # Pydantic object
                    role_val = response.role.value if hasattr(response.role, 'value') else str(response.role)
                    processed_roles.append(role_val)
                elif isinstance(response, dict):
                    # Dict object (fallback handling)
                    role_val = response.get('role', 'UNKNOWN')
                    processed_roles.append(role_val)

            return ResponseStatus(
                success=True,
                count=len(responses),
                processed_roles=processed_roles
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test Case: Using enum values (Pydantic-consistent approach)
        responses_with_values = [
            {"message": "Hello from user", "role": "user"},                     # enum VALUE - should map to "USER"
            {"message": "Hi from assistant", "role": "assistant"},              # enum VALUE - should map to "ASSISTANT"  
            {"message": "System message", "role": "system"},                    # enum VALUE - should map to "SYSTEM"
            {"message": "Internal message", "role": "assistant_internal"},      # enum VALUE - should map to "ASSISTANT_INTERNAL"
            {"message": "Feedback message", "role": "assistant_feedback"}       # enum VALUE - should map to "ASSISTANT_FEEDBACK"
        ]

        result = await client.call_tool("send_responses", {"responses": responses_with_values})
        result_text = get_result_text(result)
        result_data = json.loads(result_text)

        # Verify the results
        assert result_data["success"] is True
        assert result_data["count"] == 5
        assert len(result_data["processedRoles"]) == 5


@pytest.mark.asyncio
async def test_enum_values_work():
    """
    Test that enum values (lowercase) work correctly with values-only schema.
    This verifies that our new Pydantic-consistent approach works.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Role(str, enum.Enum):
        USER = "user"
        ASSISTANT = "assistant"

    class Response(BaseModel):
        message: str
        role: Role = Role.USER

    class ResponseStatus(BaseModel):
        success: bool
        count: int

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def send_responses(self, responses: List[Response]) -> ResponseStatus:
            return ResponseStatus(success=True, count=len(responses))

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test with enum values (should work with values-only schema)
        responses_with_values = [
            {"message": "Hello", "role": "user"},
            {"message": "Hi", "role": "assistant"},
        ]

        result = await client.call_tool("send_responses", {"responses": responses_with_values})
        result_text = get_result_text(result)
        result_data = json.loads(result_text)

        assert result_data["success"] is True
        assert result_data["count"] == 2


@pytest.mark.asyncio
async def test_fully_capitalized_enums_work():
    """
    Test that fully capitalized enums (where name == value) work correctly.
    This verifies compatibility with enums like: Status.ACTIVE = "ACTIVE"
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Status(str, enum.Enum):
        """Status with fully capitalized values"""
        ACTIVE = "ACTIVE"
        INACTIVE = "INACTIVE"
        PENDING = "PENDING"

    class Task(BaseModel):
        name: str
        status: Status = Status.PENDING

    class TaskStatus(BaseModel):
        success: bool
        count: int

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_tasks(self, tasks: List[Task]) -> TaskStatus:
            return TaskStatus(success=True, count=len(tasks))

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test with fully capitalized enum values (should work without conversion)
        tasks_data = [
            {"name": "Task 1", "status": "ACTIVE"},
            {"name": "Task 2", "status": "INACTIVE"},
            {"name": "Task 3", "status": "PENDING"},
        ]

        result = await client.call_tool("create_tasks", {"tasks": tasks_data})
        result_text = get_result_text(result)
        result_data = json.loads(result_text)

        assert result_data["success"] is True
        assert result_data["count"] == 3
