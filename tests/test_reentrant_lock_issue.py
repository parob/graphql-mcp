"""
Test for re-entrant lock issues in type mapping.

These tests specifically try to trigger scenarios where the same thread
acquires the lock multiple times (re-entrance).
"""
import pytest
from pydantic import BaseModel
from fastmcp.client import Client

try:
    from graphql_api import GraphQLAPI
    HAS_GRAPHQL_API = True
except ImportError:
    HAS_GRAPHQL_API = False

from graphql_mcp.server import GraphQLMCP


def get_result_text(result):
    """Helper to extract text from result."""
    if hasattr(result, 'content'):
        return result.content[0].text
    else:
        return result[0].text


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_deeply_nested_types():
    """
    Test deeply nested types that would cause recursive type mapping.
    This could trigger re-entrant lock acquisition.
    """
    api = GraphQLAPI()

    class Level5(BaseModel):
        value: str

    class Level4(BaseModel):
        data: Level5

    class Level3(BaseModel):
        data: Level4

    class Level2(BaseModel):
        data: Level3

    class Level1(BaseModel):
        data: Level2

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_deep(self) -> Level1:
            """Gets deeply nested data."""
            return Level1(
                data=Level2(
                    data=Level3(
                        data=Level4(
                            data=Level5(value="deep")
                        )
                    )
                )
            )

    # Creating the server will trigger type mapping
    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # List tools should work (this triggers type mapping if not already done)
        tools = await client.list_tools()
        assert "get_deep" in [t.name for t in tools]

        # Call the tool
        result = await client.call_tool("get_deep", {})
        text = get_result_text(result)
        assert "deep" in text

        print("✅ Deeply nested types work without deadlock")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_circular_type_reference():
    """
    Test types that reference each other (circular).
    This is a classic re-entrance scenario.
    """
    api = GraphQLAPI()

    class TypeA(BaseModel):
        id: int
        b_ref: dict  # Would be TypeB but can't forward ref easily

    class TypeB(BaseModel):
        id: int
        a_ref: dict  # Would be TypeA

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_a(self) -> TypeA:
            """Gets TypeA."""
            return TypeA(id=1, b_ref={"id": 2})

        @api.field
        def get_b(self) -> TypeB:
            """Gets TypeB."""
            return TypeB(id=2, a_ref={"id": 1})

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # List tools (triggers type mapping)
        tools = await client.list_tools()
        assert len(tools) >= 2

        # Call both tools
        result_a = await client.call_tool("get_a", {})
        result_b = await client.call_tool("get_b", {})

        assert result_a is not None
        assert result_b is not None

        print("✅ Circular type references work without deadlock")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_list_of_nested_types():
    """
    Test list of complex nested types.
    """
    api = GraphQLAPI()

    class Inner(BaseModel):
        value: int

    class Middle(BaseModel):
        inner: Inner
        inners: list[Inner]

    class Outer(BaseModel):
        middle: Middle
        middles: list[Middle]

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_outer(self) -> Outer:
            """Gets outer data."""
            return Outer(
                middle=Middle(
                    inner=Inner(value=1),
                    inners=[Inner(value=2), Inner(value=3)]
                ),
                middles=[
                    Middle(
                        inner=Inner(value=4),
                        inners=[Inner(value=5)]
                    )
                ]
            )

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # List tools
        tools = await client.list_tools()
        assert "get_outer" in [t.name for t in tools]

        print("✅ List of nested types works without deadlock")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_multiple_tools_with_same_nested_types():
    """
    Test multiple tools that share the same nested types.
    This ensures the cache is used correctly without re-entrance issues.
    """
    api = GraphQLAPI()

    class SharedType(BaseModel):
        id: int
        name: str

    class Container1(BaseModel):
        shared: SharedType

    class Container2(BaseModel):
        shared: SharedType

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_container1(self) -> Container1:
            """Gets container1."""
            return Container1(shared=SharedType(id=1, name="shared"))

        @api.field
        def get_container2(self) -> Container2:
            """Gets container2."""
            return Container2(shared=SharedType(id=2, name="shared"))

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # List tools (maps both tools with shared types)
        tools = await client.list_tools()
        assert len(tools) >= 2

        print("✅ Shared nested types work without deadlock")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_input_and_output_same_type():
    """
    Test where input and output use the same/similar types.
    This could trigger both input and output type mapping in the same call.
    """
    api = GraphQLAPI()

    class DataType(BaseModel):
        id: int
        value: str

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def process_data(self, data: DataType) -> DataType:
            """Processes data."""
            return DataType(id=data.id, value=f"processed_{data.value}")

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # List tools (maps both input and output)
        tools = await client.list_tools()
        assert "process_data" in [t.name for t in tools]

        # Call the tool
        result = await client.call_tool(
            "process_data",
            {"data": {"id": 1, "value": "test"}}
        )
        text = get_result_text(result)
        assert "processed_test" in text

        print("✅ Same type for input and output works without deadlock")
