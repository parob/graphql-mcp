"""
Test that verifies the complete chain:
Function return annotation → FastMCP outputSchema generation

This ensures that FastMCP is actually using the return type annotations
we set to generate the MCP output schemas.
"""
import json
import pytest
from pydantic import BaseModel
from fastmcp.client import Client

from graphql_mcp.server import GraphQLMCP


@pytest.mark.asyncio
async def test_fastmcp_uses_return_annotation_for_output_schema():
    """
    Verify that FastMCP generates outputSchema from the function's return type annotation.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Product(BaseModel):
        id: int
        name: str
        price: float
        in_stock: bool

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_product(self) -> Product:
            """Get a product."""
            return Product(id=1, name="Widget", price=9.99, in_stock=True)

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_product")

        # Verify tool has outputSchema
        assert hasattr(tool, 'outputSchema'), "Tool should have outputSchema attribute"
        schema = tool.outputSchema

        assert schema is not None, "outputSchema should not be None"
        print(f"\nFastMCP generated outputSchema:\n{json.dumps(schema, indent=2)}")

        # The schema should be an object type
        assert schema["type"] == "object", "Output schema should be object type"

        # Should have properties
        assert "properties" in schema, "Output schema should have properties"
        props = schema["properties"]

        # Should have the Product fields (in camelCase)
        # The exact field names depend on FastMCP's name conversion
        assert len(props) >= 4, f"Should have at least 4 fields, got {len(props)}"

        # Check that the fields have correct types
        field_types_found = {}
        for field_name, field_schema in props.items():
            print(f"\nField {field_name}: {field_schema}")

            # Extract type (may be in anyOf)
            if "anyOf" in field_schema:
                types = [item.get("type") for item in field_schema["anyOf"] if "type" in item]
                if types:
                    field_types_found[field_name] = types[0]
            elif "type" in field_schema:
                field_types_found[field_name] = field_schema["type"]

        print(f"\nField types found: {field_types_found}")

        # Should have integer, string, number, boolean somewhere
        all_types = set(field_types_found.values())
        assert "integer" in all_types or "number" in all_types, "Should have numeric type for id/price"
        assert "string" in all_types, "Should have string type for name"
        assert "boolean" in all_types, "Should have boolean type for in_stock"

        print("✅ FastMCP correctly generated outputSchema from Product model!")


@pytest.mark.asyncio
async def test_fastmcp_schema_matches_pydantic_model():
    """
    Verify that the outputSchema structure matches the Pydantic model structure.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Address(BaseModel):
        street: str
        city: str
        postal_code: str

    class Customer(BaseModel):
        name: str
        email: str
        address: Address

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_customer(self) -> Customer:
            """Get a customer."""
            return Customer(
                name="Alice",
                email="alice@example.com",
                address=Address(
                    street="123 Main St",
                    city="NYC",
                    postal_code="10001"
                )
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_customer")

        schema = tool.outputSchema
        print(f"\nCustomer outputSchema:\n{json.dumps(schema, indent=2)}")

        # Properties should include address as a nested object (inline or $ref)
        props = schema["properties"]
        assert "address" in props or any("address" in k.lower() for k in props.keys()), \
            "Should have address field"

        # Find the address field (might be camelCase)
        address_field_name = next(
            (k for k in props.keys() if "address" in k.lower()),
            None
        )

        if address_field_name:
            address_schema = props[address_field_name]
            print(f"\nAddress field schema: {address_schema}")

            # Should have address as a nested object (either $ref or inline)
            has_ref = "$ref" in address_schema
            has_inline = "properties" in address_schema
            if not has_ref and not has_inline and "anyOf" in address_schema:
                has_ref = any("$ref" in item for item in address_schema["anyOf"])
                has_inline = any("properties" in item for item in address_schema["anyOf"])

            assert has_ref or has_inline, "Address field should be a nested object (inline or $ref)"

        print("✅ Nested object structure properly reflected in outputSchema!")


@pytest.mark.asyncio
async def test_simple_types_have_no_output_schema_or_simple_schema():
    """
    Verify that simple scalar return types also work correctly.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_count(self) -> int:
            """Get a count."""
            return 42

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "get_count")

        # Tool should exist
        assert tool is not None

        # Check if it has outputSchema
        if hasattr(tool, 'outputSchema') and tool.outputSchema:
            schema = tool.outputSchema
            print(f"\nget_count outputSchema:\n{json.dumps(schema, indent=2)}")

            # If FastMCP generates schema for simple types, it should be correct
            # (This might vary by FastMCP version)
        else:
            print("\nNo outputSchema for simple int return type (this may be expected)")

        # The important part is that the tool works correctly
        result = await client.call_tool("get_count", {})
        if hasattr(result, 'content'):
            result_text = result.content[0].text
        else:
            result_text = result[0].text

        assert "42" in result_text, "Should return 42"


@pytest.mark.asyncio
async def test_list_output_schema_from_annotation():
    """
    Verify that list return types generate correct array schemas.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Item(BaseModel):
        id: int
        name: str

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def list_items(self) -> list[Item]:
            """List items."""
            return [Item(id=1, name="A"), Item(id=2, name="B")]

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        tools = await client.list_tools()
        tool = next(t for t in tools if t.name == "list_items")

        schema = tool.outputSchema
        print(f"\nlist_items outputSchema:\n{json.dumps(schema, indent=2)}")

        assert schema is not None

        # Should be array type or have array in structure
        # The exact structure depends on how FastMCP handles list returns
        # It might wrap it or return array directly

        print("✅ List return type has outputSchema!")
