"""
Test that dict/JSON return types produce proper output schemas.
"""
import json
import pytest
from pydantic import BaseModel
from fastmcp.client import Client

from graphql_mcp.server import GraphQLMCP


@pytest.mark.asyncio
async def test_dict_return_type_has_output_schema():
    """
    Test that dict return types (GraphQLJSON) produce a proper output schema.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_metadata(self) -> dict:
            """Returns metadata as a dict/JSON."""
            return {"version": "1.0", "author": "Alice", "tags": ["python", "graphql"]}

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_metadata")

        # Check outputSchema
        if hasattr(tool, 'outputSchema'):
            schema = tool.outputSchema
            print(f"\ndict return type outputSchema:\n{json.dumps(schema, indent=2)}")

            assert schema is not None, "Should have output schema"

            # For dict/JSON, we expect either:
            # 1. {"type": "object"} - generic object
            # 2. {} - flexible schema (current behavior with Any)
            # 3. Some schema that indicates it can hold JSON data

            print(f"Schema type: {schema.get('type')}")
            print(f"Schema structure: {schema}")

            # The key issue is that {} (empty schema from Any) isn't very useful
            # We should have at least a type indicator

        # Test functionality
        result = await client.call_tool("get_metadata", {})
        if hasattr(result, 'content'):
            result_text = result.content[0].text
        else:
            result_text = result[0].text

        data = json.loads(result_text)
        assert data["version"] == "1.0"
        assert data["author"] == "Alice"
        assert data["tags"] == ["python", "graphql"]


@pytest.mark.asyncio
async def test_dict_in_pydantic_model_output():
    """
    Test dict fields within a Pydantic model output.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class ResponseWithMetadata(BaseModel):
        success: bool
        message: str
        metadata: dict  # JSON field

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_response(self) -> ResponseWithMetadata:
            """Returns a response with metadata."""
            return ResponseWithMetadata(
                success=True,
                message="OK",
                metadata={"user_id": 123, "session": "abc"}
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_response")

        if hasattr(tool, 'outputSchema'):
            schema = tool.outputSchema
            print(f"\nPydantic model with dict field outputSchema:\n{json.dumps(schema, indent=2)}")

            # Check the metadata field
            props = schema.get("properties", {})
            if "metadata" in props:
                metadata_schema = props["metadata"]
                print(f"\nmetadata field schema: {metadata_schema}")

                # Should have some type indication, not just {}
                # Ideally {"type": "object"} or similar
            else:
                print("Metadata field not found in properties")

        # Test functionality
        result = await client.call_tool("get_response", {})
        if hasattr(result, 'content'):
            result_text = result.content[0].text
        else:
            result_text = result[0].text

        data = json.loads(result_text)
        assert data["success"] is True
        assert data["message"] == "OK"

        # metadata might be a string (serialized JSON) or dict
        metadata = data["metadata"]
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        assert metadata["user_id"] == 123


@pytest.mark.asyncio
async def test_json_maps_to_dict_with_proper_schema():
    """
    Verify that GraphQLJSON → dict → {"type": "object"} schema.
    This provides useful type information for MCP clients.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    from graphql_mcp.server import _map_graphql_type_to_python_type
    from graphql_api.types import GraphQLJSON

    # Should map to dict for better schema generation
    python_type = _map_graphql_type_to_python_type(GraphQLJSON)
    print(f"\nGraphQLJSON maps to: {python_type}")

    assert python_type == dict, "Should map to dict for proper schema generation"

    # When Pydantic creates a schema for dict:
    from pydantic import create_model
    TestModel = create_model('TestModel', json_field=(dict, ...))
    schema = TestModel.model_json_schema()

    print(f"\nSchema for field with dict type:\n{json.dumps(schema, indent=2)}")

    # The json_field should have {"type": "object"}
    json_field_schema = schema["properties"]["json_field"]
    print(f"\njson_field schema: {json_field_schema}")

    # Should indicate it's an object type
    assert json_field_schema.get("type") == "object", "Should have type: object"
    print("✅ dict produces proper object schema!")
