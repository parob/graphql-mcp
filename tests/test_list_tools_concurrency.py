"""
Tests for concurrent list_tools operations in GraphQL-MCP.

These tests specifically target the "getting the tools request" which can have
race conditions when multiple clients try to list tools simultaneously,
especially in Cloud Run / serverless environments.
"""
import asyncio
import pytest
import time
import threading
from pydantic import BaseModel
from typing import Optional

try:
    from graphql_api import GraphQLAPI
    HAS_GRAPHQL_API = True
except ImportError:
    HAS_GRAPHQL_API = False

from graphql_mcp.server import GraphQLMCP
from fastmcp.client import Client


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_simple():
    """
    Test that multiple concurrent list_tools requests work correctly.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_value(self, x: int) -> int:
            """Gets a value."""
            return x * 2

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Make 20 concurrent list_tools requests
        tasks = []
        for _ in range(20):
            task = client.list_tools()
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all results are identical
        first_tools = sorted([t.name for t in results[0]])
        for result in results[1:]:
            tools = sorted([t.name for t in result])
            assert tools == first_tools, f"Tool lists differ: {tools} vs {first_tools}"

        # Verify we got the expected tool
        assert "get_value" in first_tools

        print("✅ Successfully executed 20 concurrent list_tools requests")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_with_complex_schema():
    """
    Test concurrent list_tools with a complex schema that has many types.
    This stresses the type mapping and caching system.
    """
    api = GraphQLAPI()

    class UserInput(BaseModel):
        name: str
        email: str
        age: int

    class Address(BaseModel):
        street: str
        city: str
        country: str

    class UserProfile(BaseModel):
        id: int
        name: str
        email: str
        address: Address
        tags: list[str]

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_user(self, user_id: int) -> UserProfile:
            """Gets a user profile."""
            return UserProfile(
                id=user_id,
                name="Test User",
                email="test@example.com",
                address=Address(
                    street="123 Main St",
                    city="Test City",
                    country="US"),
                tags=[
                    "tag1",
                    "tag2"])

        @api.field
        def create_user(self, input: UserInput) -> dict:
            """Creates a user."""
            return {"id": 1, "name": input.name}

        @api.field
        def list_users(self, limit: Optional[int] = None) -> list[UserProfile]:
            """Lists users."""
            return []

        @api.field
        def search_users(
                self,
                query: str,
                filters: Optional[dict] = None) -> list[UserProfile]:
            """Searches users."""
            return []

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Make 30 concurrent list_tools requests
        tasks = []
        for _ in range(30):
            task = client.list_tools()
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all results are identical
        first_tools = sorted([t.name for t in results[0]])
        for i, result in enumerate(results[1:], 1):
            tools = sorted([t.name for t in result])
            assert tools == first_tools, f"Request {i}: Tool lists differ: {tools} vs {first_tools}"

        # Verify we got all expected tools
        expected_tools = {
            "get_user",
            "create_user",
            "list_users",
            "search_users"}
        assert expected_tools.issubset(
            set(first_tools)), f"Missing tools: {
            expected_tools - set(first_tools)}"

        print("✅ Successfully executed 30 concurrent list_tools requests with complex schema")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_with_delays():
    """
    Test concurrent list_tools with artificial delays to reveal race conditions.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def operation1(self, x: int) -> int:
            """Operation 1."""
            return x

        @api.field
        def operation2(self, y: str) -> str:
            """Operation 2."""
            return y

        @api.field
        def operation3(self, z: float) -> float:
            """Operation 3."""
            return z

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Make concurrent list_tools requests with small delays between them
        async def list_with_delay(delay_ms: int):
            await asyncio.sleep(delay_ms / 1000.0)
            return await client.list_tools()

        tasks = []
        for i in range(25):
            # Stagger the requests with varying delays
            delay = (i * 5) % 50  # 0-45ms delays
            task = list_with_delay(delay)
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all results are identical
        first_tools = sorted([t.name for t in results[0]])
        for i, result in enumerate(results[1:], 1):
            tools = sorted([t.name for t in result])
            assert tools == first_tools, f"Request {i}: Tool lists differ"

        assert len(first_tools) == 3
        print("✅ Successfully executed 25 staggered concurrent list_tools requests")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_stress():
    """
    Stress test with many concurrent list_tools requests.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def test_tool(self, value: int) -> int:
            """Test tool."""
            return value

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Make 100 concurrent list_tools requests
        start_time = time.time()

        tasks = []
        for _ in range(100):
            task = client.list_tools()
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # Verify all results are identical
        first_tools = sorted([t.name for t in results[0]])
        for result in results:
            tools = sorted([t.name for t in result])
            assert tools == first_tools

        print(
            f"✅ Stress test: 100 concurrent list_tools requests in {
                elapsed:.2f}s")
        print(f"   Throughput: {100 / elapsed:.1f} requests/second")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_with_tool_calls():
    """
    Test concurrent list_tools mixed with tool calls.
    This simulates real-world usage where clients list tools and call them.
    """
    api = GraphQLAPI()

    call_count = {"value": 0}
    lock = threading.Lock()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def increment(self) -> int:
            """Increments counter."""
            with lock:
                call_count["value"] += 1
                return call_count["value"]

        @api.field
        def get_count(self) -> int:
            """Gets count."""
            with lock:
                return call_count["value"]

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        call_count["value"] = 0

        # Mix of list_tools and tool calls
        tasks = []

        # 10 list_tools requests
        for _ in range(10):
            tasks.append(client.list_tools())

        # 10 increment calls
        for _ in range(10):
            tasks.append(client.call_tool("increment", {}))

        # 10 more list_tools requests
        for _ in range(10):
            tasks.append(client.list_tools())

        # Execute all concurrently
        results = await asyncio.gather(*tasks)

        # Separate list_tools results from tool call results
        list_tools_results = [r for r in results if isinstance(r, list)]
        tool_call_results = [r for r in results if not isinstance(r, list)]

        # Verify all list_tools results are identical
        first_tools = sorted([t.name for t in list_tools_results[0]])
        for result in list_tools_results[1:]:
            tools = sorted([t.name for t in result])
            assert tools == first_tools

        # Verify we have the expected number of results
        assert len(list_tools_results) == 20
        assert len(tool_call_results) == 10

        # Verify tool calls worked
        final_count = await client.call_tool("get_count", {})
        final_text = str(final_count)
        assert "10" in final_text

        print("✅ Successfully executed 20 list_tools + 10 tool calls concurrently")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_with_enums():
    """
    Test concurrent list_tools with enums in the schema.
    Enums have special handling in type mapping that could have race conditions.
    """
    api = GraphQLAPI()

    from enum import Enum

    class Status(str, Enum):
        ACTIVE = "active"
        INACTIVE = "inactive"
        PENDING = "pending"

    class Priority(int, Enum):
        LOW = 1
        MEDIUM = 2
        HIGH = 3

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_by_status(self, status: Status) -> str:
            """Gets by status."""
            return f"Status: {status.value}"

        @api.field
        def get_by_priority(self, priority: Priority) -> int:
            """Gets by priority."""
            return priority.value

        @api.field
        def filter_items(
                self,
                statuses: list[Status],
                priorities: list[Priority]) -> dict:
            """Filters items."""
            return {"count": len(statuses) + len(priorities)}

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Make 40 concurrent list_tools requests
        tasks = []
        for _ in range(40):
            task = client.list_tools()
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all results are identical
        first_tools = sorted([t.name for t in results[0]])
        for result in results:
            tools = sorted([t.name for t in result])
            assert tools == first_tools

        # Verify enum tools are present
        assert "get_by_status" in first_tools
        assert "get_by_priority" in first_tools
        assert "filter_items" in first_tools

        print("✅ Successfully executed 40 concurrent list_tools requests with enum schema")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_burst_pattern():
    """
    Test burst pattern of list_tools requests.
    Simulates multiple clients connecting at once (like in Cloud Run cold start).
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def test_operation(self, value: int) -> int:
            """Test operation."""
            return value * 2

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Simulate 3 bursts of 20 list_tools requests each
        for burst in range(3):
            burst_start = time.time()

            tasks = []
            for _ in range(20):
                task = client.list_tools()
                tasks.append(task)

            results = await asyncio.gather(*tasks)
            burst_elapsed = time.time() - burst_start

            # Verify all results in burst are identical
            first_tools = sorted([t.name for t in results[0]])
            for result in results[1:]:
                tools = sorted([t.name for t in result])
                assert tools == first_tools

            print(
                f"   Burst {
                    burst +
                    1}: 20 list_tools requests in {
                    burst_elapsed:.2f}s")

            # Small pause between bursts
            if burst < 2:
                await asyncio.sleep(0.05)

        print("✅ Successfully handled 3 bursts of 20 concurrent list_tools requests")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_with_nested_types():
    """
    Test concurrent list_tools with deeply nested types.
    Nested types stress the recursive type mapping system.
    """
    api = GraphQLAPI()

    class Level3(BaseModel):
        value: str

    class Level2(BaseModel):
        data: Level3
        items: list[str]

    class Level1(BaseModel):
        nested: Level2
        values: list[Level2]

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_nested(self, input: Level1) -> Level1:
            """Gets nested data."""
            return input

        @api.field
        def process_nested(self, data: list[Level1]) -> dict:
            """Processes nested data."""
            return {"count": len(data)}

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Make 35 concurrent list_tools requests
        tasks = []
        for _ in range(35):
            task = client.list_tools()
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all results are identical
        first_tools = sorted([t.name for t in results[0]])
        for result in results:
            tools = sorted([t.name for t in result])
            assert tools == first_tools

        assert "get_nested" in first_tools
        assert "process_nested" in first_tools

        print("✅ Successfully executed 35 concurrent list_tools requests with nested types")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_concurrent_list_tools_cold_start_simulation():
    """
    Simulate Cloud Run cold start where many clients connect simultaneously
    and all try to list tools at once.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def health_check(self) -> str:
            """Health check."""
            return "ok"

        @api.field
        def get_data(self, id: int) -> dict:
            """Gets data."""
            return {"id": id}

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    # Simulate 50 clients connecting at once (cold start scenario)
    start_time = time.time()

    async def client_session():
        """Simulate a client connecting and listing tools."""
        async with Client(mcp_server) as client:
            tools = await client.list_tools()
            return sorted([t.name for t in tools])

    # All clients connect and list tools simultaneously
    tasks = [client_session() for _ in range(50)]
    results = await asyncio.gather(*tasks)
    elapsed = time.time() - start_time

    # Verify all results are identical
    first_tools = results[0]
    for result in results[1:]:
        assert result == first_tools, "Tool lists differ in cold start scenario"

    assert "health_check" in first_tools
    assert "get_data" in first_tools

    print(
        f"✅ Cold start simulation: 50 simultaneous client connections in {
            elapsed:.2f}s")
    print(f"   Throughput: {50 / elapsed:.1f} connections/second")
