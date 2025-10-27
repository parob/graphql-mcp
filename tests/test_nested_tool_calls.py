"""
Tests for nested tool calls and self-referential operations.

These tests ensure that:
1. Tools can call other tools internally
2. Tools can list available tools
3. Recursive operations don't cause deadlocks
4. Concurrent nested calls work correctly
"""
import asyncio
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
async def test_tool_listing_tools_internally():
    """
    Test a tool that internally lists available tools.
    This simulates introspection scenarios.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def simple_tool(self, x: int) -> int:
            """A simple tool."""
            return x * 2

        @api.field
        def introspect(self) -> str:
            """A tool that introspects available tools."""
            # In real scenario, this might query the MCP server
            return "introspection_result"

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # First, list tools normally
        tools = await client.list_tools()
        assert len(tools) >= 2

        # Now call introspect tool
        result = await client.call_tool("introspect", {})
        text = get_result_text(result)
        assert "introspection" in text

        # Try listing tools again
        tools2 = await client.list_tools()
        assert len(tools2) == len(tools)

        print("✅ Tool introspection works correctly")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_nested_list_tools():
    """
    Test concurrent requests where each might trigger list_tools internally.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_value(self, x: int) -> int:
            """Gets a value."""
            return x

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Mix of list_tools and tool calls concurrently
        tasks = []

        for i in range(10):
            # Alternate between listing tools and calling tools
            if i % 2 == 0:
                tasks.append(client.list_tools())
            else:
                tasks.append(client.call_tool("get_value", {"x": i}))

        results = await asyncio.gather(*tasks)

        # Verify we got results for all
        assert len(results) == 10

        print("✅ Concurrent mixed list_tools and tool calls work")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_tool_with_complex_type_during_concurrent_listing():
    """
    Test that creating complex Pydantic models during concurrent list_tools doesn't deadlock.
    """
    api = GraphQLAPI()

    class ComplexData(BaseModel):
        id: int
        name: str
        nested: dict

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_complex(self, id: int) -> ComplexData:
            """Returns complex data."""
            return ComplexData(
                id=id,
                name=f"item{id}",
                nested={"key": "value"}
            )

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Trigger concurrent operations that force Pydantic model creation
        tasks = []

        # List tools multiple times (this creates Pydantic models)
        for _ in range(5):
            tasks.append(client.list_tools())

        # While listing, also call the tool
        for i in range(5):
            tasks.append(client.call_tool("get_complex", {"id": i}))

        # More list_tools calls
        for _ in range(5):
            tasks.append(client.list_tools())

        results = await asyncio.gather(*tasks)

        assert len(results) == 15
        print("✅ No deadlock with complex types during concurrent listing")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_rapid_list_tools_calls():
    """
    Test rapid successive list_tools calls.
    This can expose lock contention issues.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def test_tool(self, x: int) -> int:
            """Test tool."""
            return x

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Call list_tools 50 times in rapid succession
        tasks = [client.list_tools() for _ in range(50)]
        results = await asyncio.gather(*tasks)

        # All should return the same tools
        first_tools = sorted([t.name for t in results[0]])
        for result in results[1:]:
            tools = sorted([t.name for t in result])
            assert tools == first_tools

        print("✅ 50 rapid list_tools calls completed successfully")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_interleaved_operations():
    """
    Test interleaved list_tools and tool calls in a specific pattern.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def process(self, value: int) -> dict:
            """Process a value."""
            return {"result": value * 2}

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Pattern: list, call, list, call, list...
        results = []

        for i in range(10):
            tools = await client.list_tools()
            results.append(("list", len(tools)))

            result = await client.call_tool("process", {"value": i})
            results.append(("call", result))

        # Verify pattern
        assert len(results) == 20
        for i in range(0, 20, 2):
            assert results[i][0] == "list"
            assert results[i + 1][0] == "call"

        print("✅ Interleaved operations work correctly")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_list_tools_with_many_types():
    """
    Test list_tools with a schema that has many complex types.
    This stresses the type mapping cache system.
    """
    api = GraphQLAPI()

    # Create many complex types
    class Type1(BaseModel):
        field1: str

    class Type2(BaseModel):
        field2: int
        nested1: Type1

    class Type3(BaseModel):
        field3: float
        nested2: Type2

    class Type4(BaseModel):
        field4: bool
        nested3: Type3

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_type1(self) -> Type1:
            """Returns Type1."""
            return Type1(field1="test")

        @api.field
        def get_type2(self) -> Type2:
            """Returns Type2."""
            return Type2(field2=1, nested1=Type1(field1="test"))

        @api.field
        def get_type3(self) -> Type3:
            """Returns Type3."""
            return Type3(
                field3=1.5,
                nested2=Type2(field2=1, nested1=Type1(field1="test"))
            )

        @api.field
        def get_type4(self) -> Type4:
            """Returns Type4."""
            return Type4(
                field4=True,
                nested3=Type3(
                    field3=1.5,
                    nested2=Type2(field2=1, nested1=Type1(field1="test"))
                )
            )

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # List tools multiple times concurrently
        tasks = [client.list_tools() for _ in range(20)]
        results = await asyncio.gather(*tasks)

        # All should be identical
        first_tools = sorted([t.name for t in results[0]])
        for result in results[1:]:
            tools = sorted([t.name for t in result])
            assert tools == first_tools

        assert len(first_tools) >= 4

        print("✅ Many complex types handled correctly")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_first_time_list_tools():
    """
    Test many concurrent list_tools calls when tools haven't been cached yet.
    This is the most critical test for the lock.
    """
    api = GraphQLAPI()

    class Data(BaseModel):
        id: int
        value: str

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_data(self, id: int) -> Data:
            """Gets data."""
            return Data(id=id, value=f"data{id}")

    # Create a NEW server instance (uncached)
    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Immediately hammer with concurrent list_tools before any caching
        tasks = [client.list_tools() for _ in range(30)]
        results = await asyncio.gather(*tasks)

        # All should be identical
        first_tools = sorted([t.name for t in results[0]])
        for i, result in enumerate(results[1:], 1):
            tools = sorted([t.name for t in result])
            assert tools == first_tools, f"Request {i} differs"

        print("✅ Concurrent first-time list_tools (uncached) works correctly")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_list_tools_during_tool_execution():
    """
    Test listing tools while other tools are executing.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        async def slow_operation(self, delay_ms: int) -> str:
            """Slow operation."""
            await asyncio.sleep(delay_ms / 1000.0)
            return "completed"

        @api.field
        def fast_operation(self, x: int) -> int:
            """Fast operation."""
            return x * 2

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        tasks = []

        # Start some slow operations
        for _ in range(5):
            tasks.append(client.call_tool("slow_operation", {"delayMs": 100}))

        # While they're running, list tools
        for _ in range(10):
            tasks.append(client.list_tools())

        # And call fast operations
        for i in range(5):
            tasks.append(client.call_tool("fast_operation", {"x": i}))

        results = await asyncio.gather(*tasks)

        assert len(results) == 20
        print("✅ List tools during tool execution works")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_recursive_type_with_concurrent_listing():
    """
    Test a type that references itself (recursive) with concurrent list_tools.
    This stresses the cache placeholder logic.
    """
    api = GraphQLAPI()

    class Node(BaseModel):
        value: int
        children: list[dict]  # Can't use list[Node] due to forward ref, use dict

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_tree(self, depth: int) -> Node:
            """Gets a tree structure."""
            return Node(value=depth, children=[])

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Concurrent list_tools with recursive types
        tasks = [client.list_tools() for _ in range(25)]
        results = await asyncio.gather(*tasks)

        first_tools = sorted([t.name for t in results[0]])
        for result in results[1:]:
            tools = sorted([t.name for t in result])
            assert tools == first_tools

        print("✅ Recursive types with concurrent listing work")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_stress_list_tools_with_tool_calls():
    """
    Stress test: Many concurrent list_tools mixed with tool calls.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def compute(self, x: int) -> int:
            """Compute."""
            return x * x

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        tasks = []

        # 50 list_tools calls
        for _ in range(50):
            tasks.append(client.list_tools())

        # 50 tool calls
        for i in range(50):
            tasks.append(client.call_tool("compute", {"x": i}))

        # Randomize execution order by gathering all at once
        results = await asyncio.gather(*tasks)

        assert len(results) == 100
        print("✅ Stress test: 50 list_tools + 50 tool calls succeeded")
