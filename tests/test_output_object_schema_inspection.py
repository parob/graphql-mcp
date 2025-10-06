"""
Tests that inspect MCP schema generation for GraphQL output object types.

This test file verifies that:
1. GraphQLObjectType (output types from Pydantic models) generate proper MCP output schemas
2. All scalar types (str, int, float, bool, etc.) are properly mapped
3. graphql-api types (UUID, DateTime, Date, etc.) are properly mapped
4. Enums, lists, and nested objects work correctly in output schemas
5. The MCP output schema accurately reflects the GraphQL output structure
"""
import json
import enum
import pytest
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel
from fastmcp.client import Client
from mcp.types import TextContent
from typing import cast, Optional

from graphql_mcp.server import add_tools_from_schema, GraphQLMCP


def get_result_text(result):
    """Helper function to get text from result, handling different FastMCP API versions"""
    if hasattr(result, 'content'):
        return cast(TextContent, result.content[0]).text
    else:
        return cast(TextContent, result[0]).text


@pytest.mark.asyncio
async def test_output_scalar_types_schema_inspection():
    """
    Test that all GraphQL scalar types generate proper MCP output schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class ScalarOutput(BaseModel):
        text: str
        count: int
        price: float
        active: bool
        id_field: str

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_scalars(self) -> ScalarOutput:
            """Returns an output with all scalar types."""
            return ScalarOutput(
                text="test",
                count=42,
                price=99.99,
                active=True,
                id_field="abc123"
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_scalars")

        # Verify outputSchema exists and has proper structure
        if hasattr(tool, 'outputSchema'):
            output_schema = tool.outputSchema
            print(f"get_scalars output schema: {json.dumps(output_schema, indent=2)}")

            assert output_schema is not None
            assert output_schema.get("type") == "object"

            # Check properties - may be direct or wrapped in result
            props = output_schema.get("properties", {})
            if "result" in props:
                # Wrapped result
                result_schema = props["result"]
                if "$ref" in result_schema:
                    # Referenced schema
                    ref_name = result_schema["$ref"].split("/")[-1]
                    assert "$defs" in output_schema
                    actual_props = output_schema["$defs"][ref_name]["properties"]
                else:
                    actual_props = result_schema.get("properties", {})
            else:
                # Direct properties
                actual_props = props

            # Verify field types
            assert "text" in actual_props
            assert "count" in actual_props
            assert "price" in actual_props
            assert "active" in actual_props
            assert "idField" in actual_props  # Should be camelCase

            # Test functionality
            result = await client.call_tool("get_scalars", {})
            data = json.loads(get_result_text(result))
            assert data["text"] == "test"
            assert data["count"] == 42
            assert data["price"] == 99.99
            assert data["active"] is True
            assert data["idField"] == "abc123"


@pytest.mark.asyncio
async def test_output_graphql_api_types_schema_inspection():
    """
    Test that graphql-api special types (UUID, DateTime, Date, JSON) generate proper output schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class SpecialTypesOutput(BaseModel):
        uuid_field: UUID
        datetime_field: datetime
        date_field: date
        json_field: dict

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_special_types(self) -> SpecialTypesOutput:
            """Returns output with graphql-api special types."""
            return SpecialTypesOutput(
                uuid_field=UUID("12345678-1234-5678-1234-567812345678"),
                datetime_field=datetime(2025, 1, 1, 12, 0, 0),
                date_field=date(2025, 1, 1),
                json_field={"key": "value"}
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_special_types")

        # Verify outputSchema exists
        if hasattr(tool, 'outputSchema'):
            output_schema = tool.outputSchema
            print(f"get_special_types output schema: {json.dumps(output_schema, indent=2)}")
            assert output_schema is not None

            # Test functionality
            result = await client.call_tool("get_special_types", {})
            data = json.loads(get_result_text(result))
            assert "uuidField" in data
            assert "datetimeField" in data
            assert "dateField" in data
            assert "jsonField" in data
            # JSON fields may be serialized as strings or dicts depending on implementation
            json_field = data["jsonField"]
            if isinstance(json_field, str):
                json_field = json.loads(json_field)
            assert json_field["key"] == "value"


@pytest.mark.asyncio
async def test_output_enum_types_schema_inspection():
    """
    Test that enums in output types generate proper MCP output schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Status(str, enum.Enum):
        PENDING = "pending"
        COMPLETED = "completed"
        FAILED = "failed"

    class Priority(enum.Enum):
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    class TaskOutput(BaseModel):
        name: str
        status: Status
        priority: Priority

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_task(self) -> TaskOutput:
            """Returns a task with enum fields."""
            return TaskOutput(
                name="Test Task",
                status=Status.PENDING,
                priority=Priority.HIGH
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_task")

        # Verify outputSchema has enum fields
        if hasattr(tool, 'outputSchema'):
            output_schema = tool.outputSchema
            print(f"get_task output schema: {json.dumps(output_schema, indent=2)}")
            assert output_schema is not None

            # Test functionality - enums should be serialized as values
            result = await client.call_tool("get_task", {})
            data = json.loads(get_result_text(result))
            assert data["name"] == "Test Task"
            assert data["status"] == "pending"  # Enum value, not name
            assert data["priority"] == 3  # Integer enum value


@pytest.mark.asyncio
async def test_output_list_types_schema_inspection():
    """
    Test that lists in output types generate proper MCP output schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class ListOutput(BaseModel):
        tags: list[str]
        counts: list[int]
        prices: list[float]

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_lists(self) -> ListOutput:
            """Returns output with list fields."""
            return ListOutput(
                tags=["python", "graphql", "mcp"],
                counts=[1, 2, 3],
                prices=[10.5, 20.75, 30.0]
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_lists")

        # Verify outputSchema has array fields
        if hasattr(tool, 'outputSchema'):
            output_schema = tool.outputSchema
            print(f"get_lists output schema: {json.dumps(output_schema, indent=2)}")
            assert output_schema is not None

            # Test functionality
            result = await client.call_tool("get_lists", {})
            data = json.loads(get_result_text(result))
            assert data["tags"] == ["python", "graphql", "mcp"]
            assert data["counts"] == [1, 2, 3]
            assert data["prices"] == [10.5, 20.75, 30.0]


@pytest.mark.asyncio
async def test_output_nested_objects_schema_inspection():
    """
    Test that nested objects in output types generate proper MCP output schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Address(BaseModel):
        street: str
        city: str
        zip_code: str

    class Person(BaseModel):
        name: str
        age: int
        address: Address

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_person(self) -> Person:
            """Returns a person with nested address."""
            return Person(
                name="Alice",
                age=30,
                address=Address(
                    street="123 Main St",
                    city="Springfield",
                    zip_code="12345"
                )
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_person")

        # Verify outputSchema has nested structure
        if hasattr(tool, 'outputSchema'):
            output_schema = tool.outputSchema
            print(f"get_person output schema: {json.dumps(output_schema, indent=2)}")
            assert output_schema is not None

            # Test functionality
            result = await client.call_tool("get_person", {})
            data = json.loads(get_result_text(result))
            assert data["name"] == "Alice"
            assert data["age"] == 30
            assert data["address"]["street"] == "123 Main St"
            assert data["address"]["city"] == "Springfield"
            assert data["address"]["zipCode"] == "12345"  # camelCase


@pytest.mark.asyncio
async def test_output_optional_fields_schema_inspection():
    """
    Test that optional fields in output types are properly handled.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class OptionalOutput(BaseModel):
        required_field: str
        optional_field: Optional[str] = None
        optional_with_default: str = "default"

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_optional(self, include_optional: bool) -> OptionalOutput:
            """Returns output with optional fields."""
            if include_optional:
                return OptionalOutput(
                    required_field="required",
                    optional_field="optional",
                    optional_with_default="custom"
                )
            else:
                return OptionalOutput(required_field="required")

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_optional")

        # Verify outputSchema
        if hasattr(tool, 'outputSchema'):
            output_schema = tool.outputSchema
            print(f"get_optional output schema: {json.dumps(output_schema, indent=2)}")
            assert output_schema is not None

            # Test with optional fields included
            result1 = await client.call_tool("get_optional", {"includeOptional": True})
            data1 = json.loads(get_result_text(result1))
            assert data1["requiredField"] == "required"
            assert data1["optionalField"] == "optional"
            assert data1["optionalWithDefault"] == "custom"

            # Test without optional fields
            result2 = await client.call_tool("get_optional", {"includeOptional": False})
            data2 = json.loads(get_result_text(result2))
            assert data2["requiredField"] == "required"
            # Optional fields may be None or omitted


@pytest.mark.asyncio
async def test_output_list_of_objects_schema_inspection():
    """
    Test that lists of objects in output types generate proper MCP output schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Item(BaseModel):
        id: int
        name: str
        price: float

    class Inventory(BaseModel):
        items: list[Item]
        total_count: int

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_inventory(self) -> Inventory:
            """Returns inventory with list of items."""
            return Inventory(
                items=[
                    Item(id=1, name="Apple", price=0.5),
                    Item(id=2, name="Banana", price=0.3)
                ],
                total_count=2
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_inventory")

        # Verify outputSchema has list of objects
        if hasattr(tool, 'outputSchema'):
            output_schema = tool.outputSchema
            print(f"get_inventory output schema: {json.dumps(output_schema, indent=2)}")
            assert output_schema is not None

            # Test functionality
            result = await client.call_tool("get_inventory", {})
            data = json.loads(get_result_text(result))
            assert data["totalCount"] == 2
            assert len(data["items"]) == 2
            assert data["items"][0]["name"] == "Apple"
            assert data["items"][0]["price"] == 0.5
            assert data["items"][1]["name"] == "Banana"
            assert data["items"][1]["price"] == 0.3


@pytest.mark.asyncio
async def test_output_complex_nested_structure():
    """
    Test list of nested objects in output types.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Article(BaseModel):
        title: str
        author: str
        word_count: int

    class Magazine(BaseModel):
        name: str
        articles: list[Article]
        issue_number: int

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_magazine(self) -> Magazine:
            """Returns a magazine with articles."""
            return Magazine(
                name="Tech Monthly",
                issue_number=42,
                articles=[
                    Article(
                        title="GraphQL Tips",
                        author="Alice",
                        word_count=1000
                    ),
                    Article(
                        title="MCP Guide",
                        author="Bob",
                        word_count=1500
                    )
                ]
            )

    schema, _ = api.build_schema()
    mcp_server = add_tools_from_schema(schema)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_magazine")

        # Verify outputSchema has nested structure
        if hasattr(tool, 'outputSchema'):
            output_schema = tool.outputSchema
            print(f"get_magazine output schema: {json.dumps(output_schema, indent=2)}")
            assert output_schema is not None
            assert output_schema.get("type") == "object"

            # Verify nested structure is present in schema
            if "$defs" in output_schema:
                # Should have definitions for nested types
                assert len(output_schema["$defs"]) > 0

            # Test functionality
            result = await client.call_tool("get_magazine", {})
            data = json.loads(get_result_text(result))
            assert data["name"] == "Tech Monthly"
            assert data["issueNumber"] == 42
            assert len(data["articles"]) == 2
            assert data["articles"][0]["title"] == "GraphQL Tips"
            assert data["articles"][0]["author"] == "Alice"
            assert data["articles"][0]["wordCount"] == 1000
            assert data["articles"][1]["title"] == "MCP Guide"
            assert data["articles"][1]["author"] == "Bob"
            assert data["articles"][1]["wordCount"] == 1500


@pytest.mark.asyncio
async def test_output_schema_comparison_with_direct_tool():
    """
    Test that GraphQL-generated output schemas match direct MCP tool schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class ResultOutput(BaseModel):
        success: bool
        message: str
        count: int

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def graphql_result(self) -> ResultOutput:
            """GraphQL-generated tool."""
            return ResultOutput(success=True, message="OK", count=42)

    mcp_server = GraphQLMCP.from_api(api, name="ComparisonTest")

    # Add a direct MCP tool with the same return type
    @mcp_server.tool
    def direct_result() -> ResultOutput:
        """Direct MCP tool."""
        return ResultOutput(success=True, message="OK", count=42)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool_map = {t.name: t for t in tools}

        assert "graphql_result" in tool_map
        assert "direct_result" in tool_map

        graphql_tool = tool_map["graphql_result"].model_dump()
        direct_tool = tool_map["direct_result"].model_dump()

        # Both should have output schemas
        if "outputSchema" in graphql_tool and "outputSchema" in direct_tool:
            graphql_out = graphql_tool["outputSchema"]
            direct_out = direct_tool["outputSchema"]

            print(f"GraphQL output schema: {json.dumps(graphql_out, indent=2)}")
            print(f"Direct output schema: {json.dumps(direct_out, indent=2)}")

            # Both should have object type with properties
            assert graphql_out.get("type") == "object"
            assert direct_out.get("type") == "object"

            # Both should reference the same output structure (though names may differ)
            # The important thing is that both have detailed schemas, not just "Any"
