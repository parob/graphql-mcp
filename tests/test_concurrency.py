"""
Tests for concurrent operations in GraphQL-MCP.

These tests ensure that:
1. Multiple concurrent requests are handled correctly
2. No race conditions occur
3. Results are independent and correct
4. Works correctly even on single-CPU systems
5. Async operations don't block each other
"""
import asyncio
import pytest
import time
from pydantic import BaseModel
from fastmcp.client import Client
from typing import Optional

from graphql_mcp.server import GraphQLMCP


def get_result_text(result):
    """Helper to extract text from result."""
    if hasattr(result, 'content'):
        return result.content[0].text
    else:
        return result[0].text


@pytest.mark.asyncio
async def test_concurrent_simple_queries():
    """
    Test that multiple simple queries can be executed concurrently.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_number(self, value: int) -> int:
            """Returns the input number."""
            return value

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Execute 20 concurrent requests with different values
        tasks = []
        for i in range(20):
            task = client.call_tool("get_number", {"value": i})
            tasks.append(task)

        # Wait for all to complete
        results = await asyncio.gather(*tasks)

        # Verify each result is correct
        for i, result in enumerate(results):
            text = get_result_text(result)
            assert str(i) in text, f"Expected {i}, got {text}"

        print("✅ Successfully executed 20 concurrent simple queries")


@pytest.mark.asyncio
async def test_concurrent_queries_with_delays():
    """
    Test concurrent queries that have artificial delays to simulate I/O.
    This ensures async operations don't block each other.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        async def delayed_echo(self, message: str, delay_ms: int) -> str:
            """Echoes message after a delay."""
            await asyncio.sleep(delay_ms / 1000.0)
            return f"echo:{message}"

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        start_time = time.time()

        # Launch 10 concurrent requests with 100ms delay each
        tasks = []
        for i in range(10):
            task = client.call_tool("delayed_echo", {
                "message": f"msg{i}",
                "delayMs": 100
            })
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # Verify all results
        for i, result in enumerate(results):
            text = get_result_text(result)
            assert f"echo:msg{i}" in text, f"Expected echo:msg{i}, got {text}"

        # If truly concurrent, should take ~100ms, not 1000ms (10 * 100ms)
        # Allow some overhead but ensure it's much less than sequential
        assert elapsed < 0.5, f"Took {elapsed}s, should be <0.5s for concurrent execution"
        print(
            f"✅ Completed 10 concurrent delayed queries in {
                elapsed:.2f}s (parallel execution)")


@pytest.mark.asyncio
async def test_concurrent_complex_queries():
    """
    Test concurrent queries with complex Pydantic models.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class UserData(BaseModel):
        id: int
        name: str
        email: str

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_user(self, user_id: int) -> UserData:
            """Gets user by ID."""
            return UserData(
                id=user_id,
                name=f"User{user_id}",
                email=f"user{user_id}@example.com"
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Execute 15 concurrent complex queries
        tasks = []
        for i in range(1, 16):
            task = client.call_tool("get_user", {"userId": i})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify each result
        import json
        for i, result in enumerate(results, 1):
            data = json.loads(get_result_text(result))
            assert data["id"] == i, f"Expected id={i}, got {data['id']}"
            assert data["name"] == f"User{i}"
            assert data["email"] == f"user{i}@example.com"

        print("✅ Successfully executed 15 concurrent complex queries")


@pytest.mark.asyncio
async def test_concurrent_mutations():
    """
    Test that concurrent mutations are handled correctly.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    # Shared state to track mutations (in real app this would be a database)
    mutation_log = []

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_item(self, name: str, value: int) -> str:
            """Creates an item."""
            # Simulate async operation
            mutation_log.append((name, value))
            return f"Created {name} with value {value}"

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Execute 10 concurrent mutations
        tasks = []
        for i in range(10):
            task = client.call_tool("create_item", {
                "name": f"item{i}",
                "value": i * 10
            })
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all mutations completed
        assert len(mutation_log) == 10, f"Expected 10 mutations, got {
            len(mutation_log)}"

        # Verify each result
        for i, result in enumerate(results):
            text = get_result_text(result)
            assert f"item{i}" in text
            assert str(i * 10) in text

        print("✅ Successfully executed 10 concurrent mutations")


@pytest.mark.asyncio
async def test_concurrent_mixed_operations():
    """
    Test concurrent mix of queries and mutations.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    counter = {"value": 0}

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_counter(self) -> int:
            """Gets current counter value."""
            return counter["value"]

        @api.field(mutable=True)
        def increment_counter(self, amount: int) -> int:
            """Increments counter."""
            counter["value"] += amount
            return counter["value"]

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Reset counter
        counter["value"] = 0

        # Mix of reads and writes
        tasks = []

        # 5 increments
        for i in range(5):
            tasks.append(client.call_tool("increment_counter", {"amount": 1}))

        # 5 reads
        for i in range(5):
            tasks.append(client.call_tool("get_counter", {}))

        # Execute all concurrently
        results = await asyncio.gather(*tasks)

        # Verify all completed
        assert len(results) == 10

        # Final counter should be 5 (from 5 increments)
        final_result = await client.call_tool("get_counter", {})
        final_text = get_result_text(final_result)
        assert "5" in final_text

        print("✅ Successfully executed 10 concurrent mixed operations")


@pytest.mark.asyncio
async def test_concurrent_with_errors():
    """
    Test that errors in concurrent operations don't affect other operations.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def divide(self, numerator: int, denominator: int) -> float:
            """Divides two numbers."""
            if denominator == 0:
                raise ValueError("Cannot divide by zero")
            return numerator / denominator

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Mix of valid and invalid operations
        tasks = []

        # Valid operations
        for i in range(1, 6):
            tasks.append(
                client.call_tool(
                    "divide", {
                        "numerator": 10, "denominator": i}))

        # Invalid operations (division by zero)
        for _ in range(3):
            tasks.append(
                client.call_tool(
                    "divide", {
                        "numerator": 10, "denominator": 0}))

        # Execute all (some will fail)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and failures
        successes = 0
        failures = 0

        for result in results:
            if isinstance(result, Exception):
                failures += 1
            else:
                successes += 1

        # Should have 5 successes and 3 failures
        assert successes == 5, f"Expected 5 successes, got {successes}"
        assert failures == 3, f"Expected 3 failures, got {failures}"

        print(
            f"✅ Concurrent operations with errors handled correctly: {successes} successes, {failures} failures")


@pytest.mark.asyncio
async def test_concurrent_nested_queries():
    """
    Test concurrent queries with nested objects.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    class Address(BaseModel):
        street: str
        city: str

    class Person(BaseModel):
        name: str
        age: int
        address: Address

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_person(self, person_id: int) -> Person:
            """Gets person by ID."""
            return Person(
                name=f"Person{person_id}",
                age=20 + person_id,
                address=Address(
                    street=f"{person_id} Main St",
                    city=f"City{person_id}"
                )
            )

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Execute 12 concurrent nested queries
        tasks = []
        for i in range(1, 13):
            task = client.call_tool("get_person", {"personId": i})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify each nested result
        import json
        for i, result in enumerate(results, 1):
            data = json.loads(get_result_text(result))
            assert data["name"] == f"Person{i}"
            assert data["age"] == 20 + i
            assert data["address"]["city"] == f"City{i}"

        print("✅ Successfully executed 12 concurrent nested queries")


@pytest.mark.asyncio
async def test_high_concurrency_stress():
    """
    Stress test with high number of concurrent operations.
    This ensures the system can handle many concurrent requests even on 1 CPU.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def compute(self, x: int) -> int:
            """Simple computation."""
            return x * 2 + 1

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Execute 100 concurrent requests
        num_requests = 100
        start_time = time.time()

        tasks = []
        for i in range(num_requests):
            task = client.call_tool("compute", {"x": i})
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # Verify all results
        for i, result in enumerate(results):
            text = get_result_text(result)
            expected = i * 2 + 1
            assert str(expected) in text, f"Expected {expected}, got {text}"

        print(
            f"✅ Stress test: {num_requests} concurrent requests completed in {
                elapsed:.2f}s")
        print(f"   Throughput: {num_requests / elapsed:.1f} requests/second")


@pytest.mark.asyncio
async def test_concurrent_list_returns():
    """
    Test concurrent operations that return lists.
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
        def get_items(self, count: int) -> list[Item]:
            """Returns a list of items."""
            return [Item(id=i, name=f"Item{i}") for i in range(count)]

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Execute concurrent requests for different list sizes
        tasks = []
        for size in [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]:
            task = client.call_tool("get_items", {"count": size})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify each list result
        import json
        for size, result in enumerate(results, 1):
            data = json.loads(get_result_text(result))
            assert len(
                data) == size, f"Expected list of {size}, got {len(data)}"

        print("✅ Successfully executed 10 concurrent list-returning queries")


@pytest.mark.asyncio
async def test_concurrent_with_optional_params():
    """
    Test concurrent operations with optional parameters.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def greet(self, name: str, title: Optional[str] = None) -> str:
            """Greets a person."""
            if title:
                return f"Hello, {title} {name}"
            return f"Hello, {name}"

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Mix of calls with and without optional parameter
        tasks = []

        # 5 with title
        for i in range(5):
            tasks.append(client.call_tool("greet", {
                "name": f"Person{i}",
                "title": "Dr."
            }))

        # 5 without title
        for i in range(5):
            tasks.append(client.call_tool("greet", {"name": f"Guest{i}"}))

        results = await asyncio.gather(*tasks)

        # Verify results
        for i in range(5):
            text = get_result_text(results[i])
            assert "Dr. Person" in text

        for i in range(5, 10):
            text = get_result_text(results[i])
            assert "Hello, Guest" in text
            assert "Dr." not in text

        print("✅ Successfully executed 10 concurrent queries with optional parameters")


@pytest.mark.asyncio
async def test_concurrent_dict_json_returns():
    """
    Test concurrent operations that return dict/JSON types.
    """
    try:
        from graphql_api import GraphQLAPI
    except ImportError:
        pytest.skip("graphql-api not installed")

    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_metadata(self, key: str) -> dict:
            """Returns metadata as dict."""
            return {
                "key": key,
                "value": f"value_{key}",
                "timestamp": 1234567890
            }

    mcp_server = GraphQLMCP.from_api(api)

    async with Client(mcp_server) as client:
        # Execute concurrent dict-returning queries
        tasks = []
        for i in range(15):
            task = client.call_tool("get_metadata", {"key": f"key{i}"})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify each dict result
        import json
        for i, result in enumerate(results):
            data = json.loads(get_result_text(result))
            assert data["key"] == f"key{i}"
            assert data["value"] == f"value_key{i}"
            assert data["timestamp"] == 1234567890

        print("✅ Successfully executed 15 concurrent dict/JSON-returning queries")
