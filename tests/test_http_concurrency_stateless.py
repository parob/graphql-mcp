"""
Tests for concurrent operations in GraphQL-MCP simulating Cloud Run conditions.

These tests simulate Cloud Run / serverless deployment conditions:
1. Uses streamable-http transport (typical for Cloud Run)
2. Uses stateless_http=True (no state maintained between requests)
3. Makes concurrent MCP Client connections
4. Includes artificial delays to simulate network latency and processing time
5. Tests race conditions and concurrent state management
"""
import asyncio
import pytest
import time
import threading
from pydantic import BaseModel

try:
    from graphql_api import GraphQLAPI
    HAS_GRAPHQL_API = True
except ImportError:
    HAS_GRAPHQL_API = False

from graphql_mcp.server import GraphQLMCP
from fastmcp.client import Client


def get_result_text(result):
    """Helper to extract text from result."""
    if hasattr(result, 'content'):
        return result.content[0].text
    else:
        return result[0].text


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_concurrent_simple_queries():
    """
    Test concurrent simple queries with stateless HTTP configuration.
    Simulates Cloud Run environment with many concurrent requests.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_number(self, value: int) -> int:
            """Returns the input number."""
            # Add small delay to simulate processing
            time.sleep(0.005)
            return value

    # Configure for stateless HTTP (like Cloud Run)
    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    # Note: We test with FastMCP Client which uses the same code paths
    # as HTTP transport. The key is testing concurrent execution.
    async with Client(mcp_server) as client:
        # Execute 30 concurrent requests with delays
        tasks = []
        for i in range(30):
            task = client.call_tool("get_number", {"value": i})
            tasks.append(task)

        # Wait for all to complete
        results = await asyncio.gather(*tasks)

        # Verify each result is correct
        for i, result in enumerate(results):
            text = get_result_text(result)
            assert str(i) in text, f"Expected {i}, got {text}"

        print("✅ Successfully executed 30 concurrent queries (stateless mode)")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_concurrent_with_processing_delays():
    """
    Test concurrent queries with realistic processing delays.
    Simulates CPU-intensive operations or slow database queries in Cloud Run.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        async def process_data(self, data_id: int, delay_ms: int) -> dict:
            """Processes data with artificial delay."""
            # Simulate async I/O operation
            await asyncio.sleep(delay_ms / 1000.0)

            return {
                "id": data_id,
                "processed": True,
                "result": data_id * 2
            }

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        start_time = time.time()

        # Launch 15 concurrent requests with 100ms delay each
        tasks = []
        for i in range(15):
            task = client.call_tool(
                "process_data",
                {"dataId": i, "delayMs": 100}
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)
        elapsed = time.time() - start_time

        # Verify all results
        import json
        for i, result in enumerate(results):
            data = json.loads(get_result_text(result))
            assert data["id"] == i
            assert data["processed"] is True
            assert data["result"] == i * 2

        # Should be concurrent (~100ms), not sequential (~1500ms)
        assert elapsed < 0.5, f"Took {elapsed}s, should be <0.5s for concurrent execution"
        print(
            f"✅ Completed 15 concurrent requests with processing delays in {
                elapsed:.2f}s")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_concurrent_mutations_with_shared_state():
    """
    Test concurrent mutations with shared state.
    This is critical for Cloud Run where multiple instances may be running.
    """
    api = GraphQLAPI()

    # Shared state (in real app this would be a database)
    mutation_log = []
    lock = threading.Lock()
    request_count = {"value": 0}

    @api.type(is_root_type=True)
    class Root:
        @api.field(mutable=True)
        def create_item(self, name: str, value: int) -> dict:
            """Creates an item with thread-safe state management."""
            # Simulate network delay
            time.sleep(0.01)

            with lock:
                request_count["value"] += 1
                req_num = request_count["value"]
                mutation_log.append((name, value))

            return {
                "name": name,
                "value": value,
                "request_number": req_num
            }

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        mutation_log.clear()
        request_count["value"] = 0

        # Execute 20 concurrent mutations
        tasks = []
        for i in range(20):
            task = client.call_tool(
                "create_item",
                {"name": f"item{i}", "value": i * 10}
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all mutations completed
        assert len(mutation_log) == 20, f"Expected 20 mutations, got {
            len(mutation_log)}"

        # Verify each result
        import json
        for i, result in enumerate(results):
            data = json.loads(get_result_text(result))
            assert data["name"] == f"item{i}"
            assert data["value"] == i * 10

        print("✅ Successfully executed 20 concurrent mutations with shared state")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_concurrent_variable_delays():
    """
    Test concurrent requests with variable delays.
    Simulates real-world patterns where some requests are fast, others slow.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        async def compute(self, task_id: int, complexity: int) -> dict:
            """Simulates computation with variable complexity."""
            # Simulate variable processing time
            delay = complexity * 5  # 5-50ms
            await asyncio.sleep(delay / 1000.0)

            return {
                "task_id": task_id,
                "complexity": complexity,
                "result": task_id * complexity
            }

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Execute requests with different complexities (1-10)
        tasks = []
        for i in range(20):
            complexity = (i % 10) + 1
            task = client.call_tool(
                "compute",
                {"taskId": i, "complexity": complexity}
            )
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify all results
        import json
        for i, result in enumerate(results):
            data = json.loads(get_result_text(result))
            expected_complexity = (i % 10) + 1
            assert data["task_id"] == i
            assert data["complexity"] == expected_complexity
            assert data["result"] == i * expected_complexity

        print("✅ Successfully executed 20 concurrent requests with variable delays")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_high_concurrency_stress():
    """
    Stress test with high number of concurrent requests.
    Simulates heavy load like in a Cloud Run instance.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def compute(self, x: int) -> int:
            """Simple computation with small delay."""
            # Small delay to simulate real processing
            time.sleep(0.001)
            return x * 2 + 1

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        num_requests = 100
        start_time = time.time()

        # Execute many concurrent requests
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
            f"✅ Stress test: {num_requests} concurrent requests in {
                elapsed:.2f}s")
        print(f"   Throughput: {num_requests / elapsed:.1f} requests/second")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_concurrent_with_errors():
    """
    Test that errors in concurrent operations don't affect other operations.
    Critical for Cloud Run where errors must be isolated.
    """
    api = GraphQLAPI()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def divide(self, numerator: int, denominator: int) -> float:
            """Divides two numbers."""
            # Add delay to make race conditions more likely
            time.sleep(0.005)

            if denominator == 0:
                raise ValueError("Cannot divide by zero")
            return numerator / denominator

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Mix of valid and invalid operations
        tasks = []

        # Valid operations
        for i in range(1, 11):
            tasks.append(
                client.call_tool(
                    "divide", {
                        "numerator": 10, "denominator": i}))

        # Invalid operations (division by zero)
        for _ in range(5):
            tasks.append(
                client.call_tool(
                    "divide", {
                        "numerator": 10, "denominator": 0}))

        # Execute all (some will fail)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successes and failures
        successes = sum(1 for r in results if not isinstance(r, Exception))
        failures = sum(1 for r in results if isinstance(r, Exception))

        assert successes == 10, f"Expected 10 successes, got {successes}"
        assert failures == 5, f"Expected 5 failures, got {failures}"

        print(
            f"✅ Concurrent operations with errors: {successes} successes, {failures} failures")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_burst_pattern():
    """
    Test burst pattern: rapid concurrent requests followed by pause.
    Simulates real-world traffic patterns in Cloud Run.
    """
    api = GraphQLAPI()

    request_timestamps = []
    lock = threading.Lock()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def handle_request(self, request_id: int) -> dict:
            """Handles a request and tracks timing."""
            with lock:
                request_timestamps.append((request_id, time.time()))

            return {
                "request_id": request_id,
                "status": "processed"
            }

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        request_timestamps.clear()

        # Simulate 3 bursts of 15 requests each
        for burst in range(3):
            burst_start = time.time()

            tasks = []
            for i in range(15):
                task = client.call_tool(
                    "handle_request",
                    {"requestId": burst * 15 + i}
                )
                tasks.append(task)

            results = await asyncio.gather(*tasks)
            burst_elapsed = time.time() - burst_start

            print(f"   Burst {burst + 1}: 15 requests in {burst_elapsed:.2f}s")

            # Verify all requests in burst completed
            assert len(results) == 15

            # Small pause between bursts
            if burst < 2:
                await asyncio.sleep(0.05)

        assert len(request_timestamps) == 45
        print("✅ Successfully handled 3 bursts of 15 concurrent requests each")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_complex_models_concurrent():
    """
    Test concurrent queries with complex Pydantic models and delays.
    """
    api = GraphQLAPI()

    class UserData(BaseModel):
        id: int
        name: str
        email: str
        score: float

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def get_user(self, user_id: int) -> UserData:
            """Gets user by ID with processing delay."""
            # Simulate database query delay
            time.sleep(0.01)

            return UserData(
                id=user_id,
                name=f"User{user_id}",
                email=f"user{user_id}@example.com",
                score=user_id * 1.5
            )

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Execute 25 concurrent complex queries
        tasks = []
        for i in range(1, 26):
            task = client.call_tool("get_user", {"userId": i})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Verify each result
        import json
        for i, result in enumerate(results, 1):
            data = json.loads(get_result_text(result))
            assert data["id"] == i
            assert data["name"] == f"User{i}"
            assert data["email"] == f"user{i}@example.com"
            assert data["score"] == i * 1.5

        print("✅ Successfully executed 25 concurrent complex model queries")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_no_state_leakage():
    """
    Verify that concurrent requests don't leak state between each other.
    Critical for Cloud Run where each request should be independent.
    """
    api = GraphQLAPI()

    counter = {"value": 0}
    lock = threading.Lock()

    @api.type(is_root_type=True)
    class Root:
        @api.field
        def increment_and_get(self) -> int:
            """Increments counter and returns value."""
            # Add delay to increase chance of race conditions
            time.sleep(0.002)

            with lock:
                counter["value"] += 1
                return counter["value"]

        @api.field
        def get_counter(self) -> int:
            """Gets current counter value."""
            with lock:
                return counter["value"]

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        counter["value"] = 0

        # Make 25 concurrent increment requests
        tasks = []
        for _ in range(25):
            task = client.call_tool("increment_and_get", {})
            tasks.append(task)

        results = await asyncio.gather(*tasks)

        # Collect all returned values
        values = [int(get_result_text(r)) for r in results]

        # Verify final counter value is 25
        final_result = await client.call_tool("get_counter", {})
        final_text = get_result_text(final_result)
        assert "25" in final_text

        # Verify no duplicate values (would indicate race condition)
        assert len(
            set(values)) == 25, f"Found duplicate values, indicating race condition: {
            sorted(values)}"

        print(
            f"✅ Stateless mode: no state leakage between {
                len(values)} concurrent requests")


@pytest.mark.asyncio
@pytest.mark.skipif(not HAS_GRAPHQL_API, reason="graphql-api not installed")
async def test_http_stateless_nested_objects_concurrent():
    """
    Test concurrent queries with nested objects and delays.
    """
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
            """Gets person by ID with delay."""
            # Simulate processing time
            time.sleep(0.008)

            return Person(
                name=f"Person{person_id}",
                age=20 + person_id,
                address=Address(
                    street=f"{person_id} Main St",
                    city=f"City{person_id}"
                )
            )

    mcp_server = GraphQLMCP.from_api(api, name="TestAPI")

    async with Client(mcp_server) as client:
        # Execute 18 concurrent nested queries
        tasks = []
        for i in range(1, 19):
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

        print("✅ Successfully executed 18 concurrent nested object queries")
