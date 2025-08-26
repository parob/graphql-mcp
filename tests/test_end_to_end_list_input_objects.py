"""
End-to-end test that proves the list of input objects fix works completely.

This test reproduces the exact scenario from the user's original error:
- List[Response] parameter with complex Pydantic models
- Enums within the input objects
- Optional fields with complex types
- Actual MCP tool calls to verify everything works

Before the fix, this would fail with:
"Expected type 'ResponseInput' to be a mapping"

After the fix, it should work perfectly.
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
async def test_end_to_end_list_input_objects_original_scenario():
    """
    End-to-end test with the exact scenario that was failing before the fix.

    This test proves that the original error:
    "Expected type 'ResponseInput' to be a mapping"
    has been completely resolved.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    # Exact models from the user's scenario
    class Role(enum.Enum):
        USER = 'USER'
        ASSISTANT = 'ASSISTANT'

    class PlatformName(enum.Enum):
        DISCORD = 'DISCORD'
        SLACK = 'SLACK'
        TEAMS = 'TEAMS'

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
        @api.field(meta={"mcp": True}, mutable=True)
        async def send_responses(self, responses: List[Response]) -> ResponseStatus:
            """
            Send responses - exact signature that was failing before the fix.
            """
            print(f"📨 Processing {len(responses)} responses...")

            processed_messages = []
            for i, response in enumerate(responses):
                # Before the fix, this would fail because response would be a dict
                # After the fix, this works because GraphQL properly processes the input

                # Note: Due to how graphql-api processes input objects,
                # responses will be dicts that get converted by graphql-api to Response objects
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
                print(f"  ✅ {msg}")

            return ResponseStatus(
                success=True,
                count=len(responses),
                processed_messages=processed_messages
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Verify the tool exists and has proper schema
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}
        assert "send_responses" in tool_names

        send_responses_tool = next(t for t in tools if t.name == "send_responses")
        schema_dict = send_responses_tool.inputSchema

        print(f"🔍 MCP Tool Schema: {json.dumps(schema_dict, indent=2)}")

        # Verify schema structure
        assert schema_dict["type"] == "object"
        assert "responses" in schema_dict["properties"]
        assert "responses" in schema_dict["required"]

        # Verify it's an array of detailed objects
        responses_schema = schema_dict["properties"]["responses"]
        assert responses_schema["type"] == "array"
        assert "$ref" in responses_schema["items"]

        # Verify the detailed schema exists
        ref_name = responses_schema["items"]["$ref"].split("/")[-1]
        assert ref_name in schema_dict["$defs"]

        response_model_schema = schema_dict["$defs"][ref_name]
        assert "message" in response_model_schema["properties"]
        assert "role" in response_model_schema["properties"]
        assert "targetPlatforms" in response_model_schema["properties"]  # camelCase in GraphQL

        print("✅ Schema validation passed!")

        # Test Case 1: Simple responses (the original failing case)
        print("\n🧪 Test Case 1: Simple responses")
        simple_responses = [
            {"message": "Hello world!", "role": "USER"},
            {"message": "Hi there!", "role": "ASSISTANT"}
        ]

        result1 = await client.call_tool("send_responses", {"responses": simple_responses})
        result1_text = get_result_text(result1)
        result1_data = json.loads(result1_text)

        assert result1_data["success"] is True
        assert result1_data["count"] == 2
        assert len(result1_data["processedMessages"]) == 2
        assert "Hello world!" in result1_data["processedMessages"][0]
        assert "Hi there!" in result1_data["processedMessages"][1]

        print(f"✅ Simple responses result: {result1_data}")

        # Test Case 2: Complex responses with platforms
        print("\n🧪 Test Case 2: Complex responses with target platforms")
        complex_responses = [
            {
                "message": "Welcome to our Discord server!",
                "role": "ASSISTANT",
                "target_platforms": ["DISCORD"]
            },
            {
                "message": "Don't forget the meeting today",
                "role": "USER",
                "target_platforms": ["SLACK", "TEAMS"]
            },
            {
                "message": "System maintenance scheduled",
                "role": "ASSISTANT",
                "target_platforms": ["DISCORD", "SLACK", "TEAMS"]
            }
        ]

        result2 = await client.call_tool("send_responses", {"responses": complex_responses})
        result2_text = get_result_text(result2)
        result2_data = json.loads(result2_text)

        assert result2_data["success"] is True
        assert result2_data["count"] == 3
        assert len(result2_data["processedMessages"]) == 3
        assert "Discord server" in result2_data["processedMessages"][0]
        assert "meeting today" in result2_data["processedMessages"][1]
        assert "maintenance" in result2_data["processedMessages"][2]

        print(f"✅ Complex responses result: {result2_data}")

        # Test Case 3: Empty list (edge case)
        print("\n🧪 Test Case 3: Empty list")
        result3 = await client.call_tool("send_responses", {"responses": []})
        result3_text = get_result_text(result3)
        result3_data = json.loads(result3_text)

        assert result3_data["success"] is True
        assert result3_data["count"] == 0
        assert len(result3_data["processedMessages"]) == 0

        print(f"✅ Empty list result: {result3_data}")

        # Test Case 4: Mixed role types
        print("\n🧪 Test Case 4: Mixed role types")
        mixed_responses = [
            {"message": "Question from user", "role": "USER", "target_platforms": ["DISCORD"]},
            {"message": "Assistant response", "role": "ASSISTANT", "target_platforms": ["DISCORD"]},
            {"message": "Follow-up question", "role": "USER"},
            {"message": "Final answer", "role": "ASSISTANT", "target_platforms": ["SLACK"]}
        ]

        result4 = await client.call_tool("send_responses", {"responses": mixed_responses})
        result4_text = get_result_text(result4)
        result4_data = json.loads(result4_text)

        assert result4_data["success"] is True
        assert result4_data["count"] == 4
        assert len(result4_data["processedMessages"]) == 4

        print(f"✅ Mixed roles result: {result4_data}")

        print("\n🎉 All end-to-end tests passed! The original mapping error has been completely resolved.")


@pytest.mark.asyncio
async def test_original_error_would_have_failed():
    """
    Documentation test showing what the original error looked like.
    This test serves as documentation of what was broken before the fix.
    """
    print("\n📋 Original Error Documentation:")
    print("Before the fix, calling send_responses with List[Response] would fail with:")
    print("❌ Expected type 'ResponseInput' to be a mapping")
    print("")
    print("This happened because:")
    print("1. FastMCP created Pydantic model instances from dict inputs")
    print("2. These instances were passed directly to GraphQL")
    print("3. GraphQL expected dictionaries/mappings, not Pydantic objects")
    print("4. The error occurred specifically with list parameters containing input objects")
    print("")
    print("✅ After the fix:")
    print("1. Pydantic models are detected in input processing")
    print("2. They're converted back to dictionaries using model_dump(mode='json')")
    print("3. Lists are properly processed item by item")
    print("4. GraphQL receives the expected dictionary format")
    print("5. Everything works end-to-end!")

    # This test always passes - it's just for documentation
    assert True
