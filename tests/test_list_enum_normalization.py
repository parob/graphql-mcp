"""
Test to verify that list enum fields are properly normalized.

This addresses the "unhashable type: 'list'" error that occurred when
enum fields contained lists of enum values like target_platforms: ["discord", "slack"]
"""
import json
import pytest
from pydantic import BaseModel
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast, List, Optional
import enum

from graphql_mcp.server import add_tools_from_schema


def get_result_text(result):
    """Helper function to get text from result, handling different FastMCP API versions"""
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    else:
        return cast(TextContent, result[0]).text


@pytest.mark.asyncio
async def test_list_enum_field_normalization():
    """
    Test that reproduces and fixes the 'unhashable type: list' error
    when enum fields contain lists of enum values.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    # Enum structures from the user's code
    class Role(str, enum.Enum):
        USER = "user"
        ASSISTANT = "assistant"

    class PlatformName(str, enum.Enum):
        DISCORD = "discord"
        SLACK = "slack"
        TEAMS = "teams"

    class Response(BaseModel):
        message: str
        role: Role = Role.USER
        target_platforms: Optional[List[PlatformName]] = None

    class ResponseStatus(BaseModel):
        success: bool
        count: int
        processed_messages: List[str]

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def send_responses(self, responses: List[Response]) -> ResponseStatus:
            """Send responses - this should handle list enum normalization correctly."""
            processed_messages = []
            for i, response in enumerate(responses):
                if hasattr(response, 'message'):
                    # Pydantic object
                    msg = f"Response {i + 1}: '{response.message}' from {response.role.value}"
                    if response.target_platforms:
                        platforms = [p.value for p in response.target_platforms]
                        msg += f" targeting {platforms}"
                elif isinstance(response, dict):
                    # Dict object (fallback handling)
                    msg = f"Response {i + 1}: '{response['message']}' from {response.get('role', 'UNKNOWN')}"
                    if response.get('target_platforms'):
                        msg += f" targeting {response['target_platforms']}"
                else:
                    msg = f"Response {i + 1}: {type(response)} = {response}"

                processed_messages.append(msg)

            return ResponseStatus(
                success=True,
                count=len(responses),
                processed_messages=processed_messages
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test Case: Enum values in lists (the problematic case)
        responses_with_list_enum_values = [
            {
                "message": "Welcome to Discord",
                "role": "assistant",  # enum VALUE - should map to "ASSISTANT"
                "target_platforms": ["discord", "slack"]  # enum VALUES - should map to ["DISCORD", "SLACK"]
            },
            {
                "message": "User message", 
                "role": "user",  # enum VALUE - should map to "USER"
                "target_platforms": ["teams"]  # enum VALUE - should map to ["TEAMS"]
            },
            {
                "message": "System broadcast",
                "role": "assistant",  # enum VALUE - should map to "ASSISTANT"
                "target_platforms": ["discord", "slack", "teams"]  # enum VALUES - should map to ["DISCORD", "SLACK", "TEAMS"]
            }
        ]

        # This should not raise "unhashable type: 'list'" error
        result = await client.call_tool("send_responses", {"responses": responses_with_list_enum_values})
        result_text = get_result_text(result)
        result_data = json.loads(result_text)

        # Verify the results
        assert result_data["success"] is True
        assert result_data["count"] == 3
        assert len(result_data["processedMessages"]) == 3
        
        # Check that the messages were processed (content doesn't matter as much as no crash)
        for message in result_data["processedMessages"]:
            assert isinstance(message, str)
            assert len(message) > 0


@pytest.mark.asyncio
async def test_mixed_enum_field_types():
    """
    Test that both single enum fields and list enum fields work correctly together.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Priority(str, enum.Enum):
        LOW = "low"
        HIGH = "high"

    class Tag(str, enum.Enum):
        URGENT = "urgent"
        FEATURE = "feature"
        BUG = "bug"

    class Task(BaseModel):
        title: str
        priority: Priority = Priority.LOW  # Single enum field
        tags: Optional[List[Tag]] = None   # List enum field

    class TaskResult(BaseModel):
        success: bool
        processed_count: int

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_tasks(self, tasks: List[Task]) -> TaskResult:
            return TaskResult(success=True, processed_count=len(tasks))

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test with both single enums and list enums using VALUES (lowercase)
        tasks_data = [
            {
                "title": "Fix login bug",
                "priority": "high",        # Single enum VALUE
                "tags": ["bug", "urgent"]  # List enum VALUES
            },
            {
                "title": "Add new feature", 
                "priority": "low",         # Single enum VALUE
                "tags": ["feature"]       # List enum VALUE
            },
            {
                "title": "Update docs",
                "priority": "low",         # Single enum VALUE
                "tags": ["feature"]       # List enum VALUE
            }
        ]

        # This should handle both single and list enum normalization without errors
        result = await client.call_tool("create_tasks", {"tasks": tasks_data})
        result_text = get_result_text(result)
        result_data = json.loads(result_text)

        assert result_data["success"] is True
        assert result_data["processedCount"] == 3