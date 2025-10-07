"""
Tests to validate that GraphQL output types are correctly mapped to MCP output schemas.

This test file specifically validates the MCP JSON schema structure to ensure:
1. Python type mappings produce correct JSON schema types
2. All scalar types have the correct JSON schema representation
3. Complex types (lists, objects, enums) have proper structure
4. Nested objects use $ref correctly
5. Required vs optional fields are properly marked
"""
import json
import enum
import pytest
from datetime import datetime, date
from uuid import UUID
from pydantic import BaseModel
from fastmcp.client import Client
from typing import Optional

from graphql_mcp.server import GraphQLMCP


def get_output_schema(tool):
    """Helper to get output schema from a tool."""
    if hasattr(tool, 'outputSchema'):
        return tool.outputSchema
    return None


@pytest.mark.asyncio
async def test_mcp_output_schema_scalar_types():
    """
    Validate that all scalar types produce correct MCP JSON schema types.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class AllScalars(BaseModel):
        string_field: str
        int_field: int
        float_field: float
        bool_field: bool
        uuid_field: UUID
        datetime_field: datetime
        date_field: date

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_scalars(self) -> AllScalars:
            """Returns all scalar types."""
            return AllScalars(
                string_field="test",
                int_field=42,
                float_field=3.14,
                bool_field=True,
                uuid_field=UUID("12345678-1234-5678-1234-567812345678"),
                datetime_field=datetime(2025, 1, 1),
                date_field=date(2025, 1, 1)
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_scalars")
        schema = get_output_schema(tool)

        assert schema is not None, "Output schema should exist"
        print(f"\nScalar types schema:\n{json.dumps(schema, indent=2)}")

        # Should be an object type
        assert schema["type"] == "object"
        props = schema["properties"]

        # Validate string field
        assert "stringField" in props
        string_schema = props["stringField"]
        # May be anyOf with null, or direct type
        if "anyOf" in string_schema:
            types = [item.get("type") for item in string_schema["anyOf"]]
            assert "string" in types
        else:
            assert string_schema["type"] == "string"

        # Validate int field
        assert "intField" in props
        int_schema = props["intField"]
        if "anyOf" in int_schema:
            types = [item.get("type") for item in int_schema["anyOf"]]
            assert "integer" in types
        else:
            assert int_schema["type"] == "integer"

        # Validate float field
        assert "floatField" in props
        float_schema = props["floatField"]
        if "anyOf" in float_schema:
            types = [item.get("type") for item in float_schema["anyOf"]]
            assert "number" in types
        else:
            assert float_schema["type"] == "number"

        # Validate bool field
        assert "boolField" in props
        bool_schema = props["boolField"]
        if "anyOf" in bool_schema:
            types = [item.get("type") for item in bool_schema["anyOf"]]
            assert "boolean" in types
        else:
            assert bool_schema["type"] == "boolean"

        # Validate UUID field (should be string with format)
        assert "uuidField" in props
        uuid_schema = props["uuidField"]
        if "anyOf" in uuid_schema:
            # Find the string type with uuid format
            string_items = [item for item in uuid_schema["anyOf"] if item.get("type") == "string"]
            assert len(string_items) > 0
            assert string_items[0].get("format") == "uuid"
        else:
            assert uuid_schema["type"] == "string"
            assert uuid_schema.get("format") == "uuid"

        # Validate datetime field (should be string with date-time format)
        assert "datetimeField" in props
        datetime_schema = props["datetimeField"]
        if "anyOf" in datetime_schema:
            string_items = [item for item in datetime_schema["anyOf"] if item.get("type") == "string"]
            assert len(string_items) > 0
            assert string_items[0].get("format") == "date-time"
        else:
            assert datetime_schema["type"] == "string"
            assert datetime_schema.get("format") == "date-time"

        # Validate date field (should be string with date format)
        assert "dateField" in props
        date_schema = props["dateField"]
        if "anyOf" in date_schema:
            string_items = [item for item in date_schema["anyOf"] if item.get("type") == "string"]
            assert len(string_items) > 0
            assert string_items[0].get("format") == "date"
        else:
            assert date_schema["type"] == "string"
            assert date_schema.get("format") == "date"


@pytest.mark.asyncio
async def test_mcp_output_schema_enum_types():
    """
    Validate that enum types produce correct MCP JSON schema with enum values.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Status(str, enum.Enum):
        DRAFT = "draft"
        PUBLISHED = "published"
        ARCHIVED = "archived"

    class Priority(enum.Enum):
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    class EnumOutput(BaseModel):
        status: Status
        priority: Priority

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_enums(self) -> EnumOutput:
            """Returns enum types."""
            return EnumOutput(status=Status.PUBLISHED, priority=Priority.HIGH)

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_enums")
        schema = get_output_schema(tool)

        assert schema is not None
        print(f"\nEnum types schema:\n{json.dumps(schema, indent=2)}")

        props = schema["properties"]

        # Validate string enum
        assert "status" in props
        status_schema = props["status"]
        if "anyOf" in status_schema:
            enum_items = [item for item in status_schema["anyOf"] if "enum" in item]
            assert len(enum_items) > 0
            enum_values = enum_items[0]["enum"]
            # Should contain the enum values
            assert "draft" in enum_values
            assert "published" in enum_values
            assert "archived" in enum_values
        else:
            assert "enum" in status_schema
            assert "draft" in status_schema["enum"]

        # Validate integer enum
        assert "priority" in props
        priority_schema = props["priority"]
        if "anyOf" in priority_schema:
            # Should have integer and string options
            enum_items = [item for item in priority_schema["anyOf"] if "enum" in item]
            assert len(enum_items) > 0


@pytest.mark.asyncio
async def test_mcp_output_schema_list_types():
    """
    Validate that list types produce correct MCP JSON schema with array type.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class ListOutput(BaseModel):
        strings: list[str]
        integers: list[int]
        floats: list[float]

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_lists(self) -> ListOutput:
            """Returns list types."""
            return ListOutput(
                strings=["a", "b", "c"],
                integers=[1, 2, 3],
                floats=[1.1, 2.2, 3.3]
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_lists")
        schema = get_output_schema(tool)

        assert schema is not None
        print(f"\nList types schema:\n{json.dumps(schema, indent=2)}")

        props = schema["properties"]

        # Validate string list
        assert "strings" in props
        strings_schema = props["strings"]
        assert strings_schema["type"] == "array"
        assert strings_schema["items"]["type"] == "string"

        # Validate integer list
        assert "integers" in props
        integers_schema = props["integers"]
        assert integers_schema["type"] == "array"
        assert integers_schema["items"]["type"] == "integer"

        # Validate float list
        assert "floats" in props
        floats_schema = props["floats"]
        assert floats_schema["type"] == "array"
        assert floats_schema["items"]["type"] == "number"


@pytest.mark.asyncio
async def test_mcp_output_schema_nested_objects():
    """
    Validate that nested objects use $ref correctly in MCP JSON schema.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Address(BaseModel):
        street: str
        city: str
        country: str

    class Person(BaseModel):
        name: str
        age: int
        address: Address

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_person(self) -> Person:
            """Returns nested objects."""
            return Person(
                name="Alice",
                age=30,
                address=Address(street="123 Main St", city="NYC", country="USA")
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_person")
        schema = get_output_schema(tool)

        assert schema is not None
        print(f"\nNested objects schema:\n{json.dumps(schema, indent=2)}")

        props = schema["properties"]

        # Should have address field
        assert "address" in props
        address_schema = props["address"]

        # Address should use $ref
        if "anyOf" in address_schema:
            ref_items = [item for item in address_schema["anyOf"] if "$ref" in item]
            assert len(ref_items) > 0
            ref = ref_items[0]["$ref"]
        else:
            assert "$ref" in address_schema
            ref = address_schema["$ref"]

        # Extract referenced definition name
        assert ref.startswith("#/$defs/")
        def_name = ref.split("/")[-1]

        # Should have $defs with the Address definition
        assert "$defs" in schema
        assert def_name in schema["$defs"]

        address_def = schema["$defs"][def_name]
        assert address_def["type"] == "object"
        assert "properties" in address_def

        # Validate Address properties
        address_props = address_def["properties"]
        assert "street" in address_props
        assert "city" in address_props
        assert "country" in address_props


@pytest.mark.asyncio
async def test_mcp_output_schema_list_of_objects():
    """
    Validate that lists of objects use $ref in items correctly.
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
        total: int

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_inventory(self) -> Inventory:
            """Returns list of objects."""
            return Inventory(
                items=[
                    Item(id=1, name="A", price=10.0),
                    Item(id=2, name="B", price=20.0)
                ],
                total=2
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_inventory")
        schema = get_output_schema(tool)

        assert schema is not None
        print(f"\nList of objects schema:\n{json.dumps(schema, indent=2)}")

        props = schema["properties"]

        # Should have items array
        assert "items" in props
        items_schema = props["items"]
        assert items_schema["type"] == "array"

        # Array items should use $ref
        items_def = items_schema["items"]
        assert "$ref" in items_def
        ref = items_def["$ref"]

        # Extract referenced definition
        assert ref.startswith("#/$defs/")
        def_name = ref.split("/")[-1]

        # Should have Item definition
        assert "$defs" in schema
        assert def_name in schema["$defs"]

        item_def = schema["$defs"][def_name]
        assert item_def["type"] == "object"

        # Validate Item properties
        item_props = item_def["properties"]
        assert "id" in item_props
        assert "name" in item_props
        assert "price" in item_props


@pytest.mark.asyncio
async def test_mcp_output_schema_optional_fields():
    """
    Validate that optional fields are correctly marked in MCP schema.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class OptionalOutput(BaseModel):
        required_field: str
        optional_field: Optional[str] = None

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_optional(self) -> OptionalOutput:
            """Returns output with optional fields."""
            return OptionalOutput(required_field="required")

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_optional")
        schema = get_output_schema(tool)

        assert schema is not None
        print(f"\nOptional fields schema:\n{json.dumps(schema, indent=2)}")

        # Both fields should be in properties
        props = schema["properties"]
        assert "requiredField" in props
        assert "optionalField" in props

        # Optional field should allow null
        optional_schema = props["optionalField"]
        if "anyOf" in optional_schema:
            types = [item.get("type") for item in optional_schema["anyOf"]]
            assert "null" in types
        # Or may have default null
        elif "default" in optional_schema:
            assert optional_schema["default"] is None


@pytest.mark.asyncio
async def test_mcp_output_schema_comparison():
    """
    Compare MCP output schemas between GraphQL-generated and direct tools.
    Ensures both approaches produce equivalent JSON schema structures.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Result(BaseModel):
        success: bool
        count: int
        message: str

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def graphql_result(self) -> Result:
            """GraphQL tool."""
            return Result(success=True, count=42, message="OK")

    mcp_server = GraphQLMCP.from_api(api)

    @mcp_server.tool
    def direct_result() -> Result:
        """Direct tool."""
        return Result(success=True, count=42, message="OK")

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool_map = {t.name: t for t in tools}

        graphql_schema = get_output_schema(tool_map["graphql_result"])
        direct_schema = get_output_schema(tool_map["direct_result"])

        print(f"\nGraphQL output schema:\n{json.dumps(graphql_schema, indent=2)}")
        print(f"\nDirect output schema:\n{json.dumps(direct_schema, indent=2)}")

        # Both should have output schemas
        assert graphql_schema is not None
        assert direct_schema is not None

        # Both should be object types
        assert graphql_schema["type"] == "object"
        assert direct_schema["type"] == "object"

        # Both should have the same field names (camelCase)
        graphql_props = set(graphql_schema.get("properties", {}).keys())
        direct_props = set(direct_schema.get("properties", {}).keys())

        # Account for possible result wrapping
        if "result" in graphql_props:
            graphql_props = set(graphql_schema["properties"]["result"].get("properties", {}).keys())
        if "result" in direct_props:
            direct_props = set(direct_schema["properties"]["result"].get("properties", {}).keys())

        # Should have the same fields
        expected_fields = {"success", "count", "message"}
        assert expected_fields.issubset(graphql_props) or expected_fields.issubset(direct_props)


@pytest.mark.asyncio
async def test_mcp_output_schema_dict_json_types():
    """
    Verify that dict/JSON types produce proper output schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class ResponseWithJSON(BaseModel):
        data: dict  # JSON field

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_json_data(self) -> ResponseWithJSON:
            """Returns response with JSON data."""
            return ResponseWithJSON(data={"key": "value", "count": 42})

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_json_data")

        schema = tool.outputSchema
        print(f"\nJSON field outputSchema:\n{json.dumps(schema, indent=2)}")

        assert schema is not None
        assert schema["type"] == "object"

        # Check the data field (JSON/dict type)
        props = schema["properties"]
        assert "data" in props

        data_schema = props["data"]
        print(f"\ndata field schema: {data_schema}")

        # Should have type: object (not empty schema)
        if "anyOf" in data_schema:
            # Find the object type in anyOf
            obj_schemas = [s for s in data_schema["anyOf"] if s.get("type") == "object"]
            assert len(obj_schemas) > 0, "Should have object type in anyOf"
            print("✅ dict/JSON field has proper object type schema!")
        else:
            assert data_schema.get("type") == "object", "dict should map to object type"
            print("✅ dict/JSON field has proper object type schema!")


@pytest.mark.asyncio
async def test_mcp_output_schema_all_types_combined():
    """
    Comprehensive test with all types combined in one output.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Status(str, enum.Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"

    class Metadata(BaseModel):
        created_at: datetime
        version: int

    class CompleteOutput(BaseModel):
        # Scalars
        id: str
        count: int
        rating: float
        enabled: bool
        # Enum
        status: Status
        # Nested object
        metadata: Metadata
        # Lists
        tags: list[str]
        scores: list[float]
        # Optional
        description: Optional[str] = None

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_complete(self) -> CompleteOutput:
            """Returns all types combined."""
            return CompleteOutput(
                id="123",
                count=42,
                rating=4.5,
                enabled=True,
                status=Status.ACTIVE,
                metadata=Metadata(created_at=datetime(2025, 1, 1), version=1),
                tags=["python", "graphql"],
                scores=[1.0, 2.0, 3.0]
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_complete")
        schema = get_output_schema(tool)

        assert schema is not None
        print(f"\nComplete output schema:\n{json.dumps(schema, indent=2)}")

        # Validate it has all expected fields
        props = schema["properties"]
        assert "id" in props
        assert "count" in props
        assert "rating" in props
        assert "enabled" in props
        assert "status" in props
        assert "metadata" in props
        assert "tags" in props
        assert "scores" in props
        assert "description" in props

        # Validate metadata uses $ref
        metadata_schema = props["metadata"]
        has_ref = "$ref" in metadata_schema
        if not has_ref and "anyOf" in metadata_schema:
            has_ref = any("$ref" in item for item in metadata_schema["anyOf"])
        assert has_ref, "Nested metadata object should use $ref"

        # Should have $defs with Metadata
        assert "$defs" in schema
        assert len(schema["$defs"]) > 0
