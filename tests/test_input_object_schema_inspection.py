"""
Tests that inspect MCP schema generation for GraphQL input object types.

This test file verifies that:
1. GraphQLInputObjectType parameters generate proper MCP tool schemas
2. JSON scalar type parameters generate proper MCP tool schemas
3. The MCP schema accurately reflects the GraphQL input structure
4. Both dict and Pydantic model inputs work with the generated schemas
"""
import json
import pytest
from pydantic import BaseModel
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast, Optional

from graphql_mcp.server import add_tools_from_schema


def resolve_object_schema(prop_schema, root_schema=None):
    """Resolve a property schema to its object definition, handling both $ref and inline."""
    if "$ref" in prop_schema:
        ref_name = prop_schema["$ref"].split("/")[-1]
        return root_schema["$defs"][ref_name]
    if "properties" in prop_schema:
        return prop_schema
    if "anyOf" in prop_schema:
        for item in prop_schema["anyOf"]:
            if "$ref" in item and root_schema:
                ref_name = item["$ref"].split("/")[-1]
                return root_schema["$defs"][ref_name]
            if "properties" in item:
                return item
    return prop_schema


def get_result_text(result):
    """Helper function to get text from result, handling different FastMCP API versions"""
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    else:
        return cast(TextContent, result[0]).text


@pytest.mark.asyncio
async def test_input_object_type_schema_inspection():
    """
    Test that GraphQLInputObjectType generates proper MCP tool schema with nested object structure.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class UserInput(BaseModel):
        name: str
        age: int
        email: str
        is_active: bool = True

    class AddressInput(BaseModel):
        street: str
        city: str
        zip_code: str

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_user(self, user_input: UserInput) -> str:
            """Creates a user with detailed input object."""
            return f"User: {user_input.name}"

        @api.field(mutable=True)
        def create_user_with_address(self, user_input: UserInput, address_input: AddressInput) -> str:
            """Creates a user with both user and address input objects."""
            return f"User: {user_input.name} at {address_input.city}"

    schema = api.schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool_names = {t.name for t in tools}

        # Verify tools exist
        assert "create_user" in tool_names
        assert "create_user_with_address" in tool_names

        # Test create_user tool schema
        create_user_tool = next(t for t in tools if t.name == "create_user")
        schema_dict = create_user_tool.inputSchema

        print(f"create_user schema: {json.dumps(schema_dict, indent=2)}")

        # Verify the schema structure for GraphQLInputObjectType
        assert schema_dict["type"] == "object"
        assert "properties" in schema_dict
        assert "userInput" in schema_dict["properties"]
        assert "required" in schema_dict
        assert "userInput" in schema_dict["required"]

        # Check that userInput has detailed object structure (inline or $ref)
        user_input_schema = schema_dict["properties"]["userInput"]
        detailed_schema = resolve_object_schema(user_input_schema, schema_dict)
        assert detailed_schema["type"] == "object"
        assert "properties" in detailed_schema

        # Verify all UserInput fields are present
        user_props = detailed_schema["properties"]
        assert "name" in user_props
        assert "age" in user_props
        assert "email" in user_props
        assert "isActive" in user_props  # Should be camelCase in schema

        # Verify field types (they may be Union types with null)
        def check_field_type(field_schema, expected_type):
            if "type" in field_schema:
                return field_schema["type"] == expected_type
            elif "anyOf" in field_schema:
                types = [item.get("type") for item in field_schema["anyOf"]]
                return expected_type in types
            return False

        assert check_field_type(user_props["name"], "string")
        assert check_field_type(user_props["age"], "integer")
        assert check_field_type(user_props["email"], "string")
        assert check_field_type(user_props["isActive"], "boolean")

        # Test create_user_with_address tool schema
        create_user_addr_tool = next(
            t for t in tools if t.name == "create_user_with_address")
        addr_schema_dict = create_user_addr_tool.inputSchema

        print(
            f"create_user_with_address schema: {json.dumps(addr_schema_dict, indent=2)}")

        # Should have both userInput and addressInput
        assert "userInput" in addr_schema_dict["properties"]
        assert "addressInput" in addr_schema_dict["properties"]
        assert set(addr_schema_dict["required"]) == {
            "userInput", "addressInput"}

        # Verify addressInput structure (inline or $ref)
        addr_input_schema = addr_schema_dict["properties"]["addressInput"]
        addr_detailed_schema = resolve_object_schema(addr_input_schema, addr_schema_dict)
        addr_props = addr_detailed_schema["properties"]
        assert "street" in addr_props
        assert "city" in addr_props
        assert "zipCode" in addr_props  # Should be camelCase


@pytest.mark.asyncio
async def test_json_scalar_type_schema_inspection():
    """
    Test that JSON scalar type generates proper MCP tool schema with generic object structure.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_item(self, input: dict) -> str:
            """Creates an item with JSON scalar input."""
            return "Item created"

        @api.field(mutable=True)
        def create_items(self, items: dict, metadata: dict) -> str:
            """Creates multiple items with multiple JSON inputs."""
            return "Items created"

    schema = api.schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()

        # Test create_item tool schema
        create_item_tool = next(t for t in tools if t.name == "create_item")
        schema_dict = create_item_tool.inputSchema

        print(
            f"create_item (JSON scalar) schema: {json.dumps(schema_dict, indent=2)}")

        # Verify the schema structure for JSON scalar type
        assert schema_dict["type"] == "object"
        assert "input" in schema_dict["properties"]
        assert "input" in schema_dict["required"]

        # Check that input has generic object structure (no nested properties)
        input_schema = schema_dict["properties"]["input"]
        # JSON scalar should be a generic object without $ref or detailed schema
        assert "$ref" not in input_schema
        # May have minimal schema info but not detailed properties
        if "type" in input_schema:
            assert input_schema["type"] == "object"
        # Should NOT have detailed properties like GraphQLInputObjectType does
        assert "properties" not in input_schema or not input_schema.get(
            "properties")

        # Test create_items tool schema
        create_items_tool = next(t for t in tools if t.name == "create_items")
        items_schema_dict = create_items_tool.inputSchema

        print(
            f"create_items (multiple JSON scalars) schema: {json.dumps(items_schema_dict, indent=2)}")

        # Should have both items and metadata as generic objects
        assert "items" in items_schema_dict["properties"]
        assert "metadata" in items_schema_dict["properties"]
        assert set(items_schema_dict["required"]) == {"items", "metadata"}


@pytest.mark.asyncio
async def test_mixed_input_types_schema_inspection():
    """
    Test that tools with both GraphQLInputObjectType and JSON scalar types generate correct schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class UserInput(BaseModel):
        name: str
        age: int

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_user_with_metadata(self, user_input: UserInput, metadata: dict, tags: list[str]) -> str:
            """Creates a user with mixed input types."""
            return "User created with metadata"

    schema = api.schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()

        tool = next(t for t in tools if t.name == "create_user_with_metadata")
        schema_dict = tool.inputSchema

        print(f"mixed input types schema: {json.dumps(schema_dict, indent=2)}")

        # Should have all three parameters
        props = schema_dict["properties"]
        assert "userInput" in props
        assert "metadata" in props
        assert "tags" in props
        assert set(schema_dict["required"]) == {
            "userInput", "metadata", "tags"}

        # userInput should have detailed object structure (inline or $ref)
        user_input_schema = props["userInput"]
        user_detailed_schema = resolve_object_schema(user_input_schema, schema_dict)
        assert "name" in user_detailed_schema["properties"]
        assert "age" in user_detailed_schema["properties"]

        # metadata should have generic object structure (JSON scalar)
        metadata_schema = props["metadata"]
        # Should NOT have detailed properties like GraphQLInputObjectType does
        assert "properties" not in metadata_schema or not metadata_schema.get(
            "properties")

        # tags should be array of strings
        tags_schema = props["tags"]
        assert tags_schema["type"] == "array"
        assert tags_schema["items"]["type"] == "string"


@pytest.mark.asyncio
async def test_functional_behavior_with_schema_inspection():
    """
    Test that the generated schemas work functionally with actual tool calls.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class UserInput(BaseModel):
        name: str
        age: int
        email: str

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def test_input_object(self, user_input: UserInput) -> str:
            """Test GraphQLInputObjectType handling."""
            assert isinstance(user_input, UserInput)
            return f"InputObject: {user_input.name} ({user_input.age}) - {user_input.email}"

        @api.field(mutable=True)
        def test_json_scalar(self, metadata: dict) -> str:
            """Test JSON scalar type handling."""
            assert isinstance(metadata, dict)
            return f"JSONScalar: {metadata.get('key')} = {metadata.get('value')}"

    schema = api.schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        # Test GraphQLInputObjectType with dict input
        user_dict = {"name": "Alice", "age": 30, "email": "alice@example.com"}
        result1 = await client.call_tool("test_input_object", {"userInput": user_dict})
        assert "InputObject: Alice (30) - alice@example.com" == get_result_text(result1)

        # Test GraphQLInputObjectType with Pydantic model input
        user_model = UserInput(name="Bob", age=25, email="bob@example.com")
        result2 = await client.call_tool("test_input_object", {"userInput": user_model})
        assert "InputObject: Bob (25) - bob@example.com" == get_result_text(result2)

        # Test JSON scalar type with dict input
        metadata_dict = {"key": "environment", "value": "production"}
        result3 = await client.call_tool("test_json_scalar", {"metadata": metadata_dict})
        assert "JSONScalar: environment = production" == get_result_text(
            result3)


@pytest.mark.asyncio
async def test_optional_input_object_schema_inspection():
    """
    Test that optional GraphQLInputObjectType parameters generate correct schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class UserInput(BaseModel):
        name: str
        age: int

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_user_maybe(self, user_input: Optional[UserInput] = None) -> str:
            """Creates a user with optional input object."""
            if user_input:
                return f"User: {user_input.name}"
            return "No user created"

    schema = api.schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()

        tool = next(t for t in tools if t.name == "create_user_maybe")
        schema_dict = tool.inputSchema

        print(
            f"optional input object schema: {json.dumps(schema_dict, indent=2)}")

        # Optional parameters should not be in required list
        assert "required" not in schema_dict or "userInput" not in schema_dict.get(
            "required", [])

        # Should still have proper object structure (inline or $ref)
        user_input_schema = schema_dict["properties"]["userInput"]
        user_detailed_schema = resolve_object_schema(user_input_schema, schema_dict)
        assert "name" in user_detailed_schema["properties"]
        assert "age" in user_detailed_schema["properties"]

        # Test that it works without input
        result1 = await client.call_tool("create_user_maybe", {})
        assert "No user created" == get_result_text(result1)

        # Note: Optional input object parameters currently pass through as dicts
        # rather than being converted to Pydantic models. This is a known limitation
        # that occurs when GraphQL input object types are not NonNull.


@pytest.mark.asyncio
async def test_list_of_input_objects_schema_inspection():
    """
    Test that lists of GraphQLInputObjectType parameters work correctly.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    import enum

    api = GraphQLAPI()

    class Status(enum.Enum):
        PENDING = 'PENDING'
        COMPLETED = 'COMPLETED'

    class TaskInput(BaseModel):
        title: str
        description: str
        status: Status = Status.PENDING

    class BatchResult(BaseModel):
        success: bool
        processed_count: int

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_tasks(self, tasks: list[TaskInput]) -> BatchResult:
            """Creates multiple tasks from a list of input objects."""
            print(f"Received tasks type: {type(tasks)}")
            if tasks and len(tasks) > 0:
                print(f"First task type: {type(tasks[0])}")
                print(f"First task: {tasks[0]}")
            return BatchResult(success=True, processed_count=len(tasks) if tasks else 0)

    schema = api.schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()

        tool = next(t for t in tools if t.name == "create_tasks")
        schema_dict = tool.inputSchema

        print(
            f"list of input objects schema: {json.dumps(schema_dict, indent=2)}")

        # Verify the schema structure for list of input objects
        assert schema_dict["type"] == "object"
        assert "tasks" in schema_dict["properties"]
        assert "tasks" in schema_dict["required"]

        # Check that tasks is an array
        tasks_schema = schema_dict["properties"]["tasks"]
        assert tasks_schema["type"] == "array"

        # Check that array items have detailed schema (inline or $ref)
        items_schema = tasks_schema["items"]
        task_detailed_schema = resolve_object_schema(items_schema, schema_dict)
        assert "title" in task_detailed_schema["properties"]
        assert "description" in task_detailed_schema["properties"]
        assert "status" in task_detailed_schema["properties"]

        # Test functionality with list of dict inputs
        tasks_data = [
            {"title": "Task 1", "description": "First task", "status": "PENDING"},
            {"title": "Task 2", "description": "Second task", "status": "COMPLETED"}
        ]

        result = await client.call_tool("create_tasks", {"tasks": tasks_data})
        result_text = get_result_text(result)
        result_json = json.loads(result_text)
        assert result_json["success"] is True
        assert result_json["processedCount"] == 2  # GraphQL uses camelCase
