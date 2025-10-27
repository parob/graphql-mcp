---
title: Testing
weight: 6
---

# Testing

Learn how to test your GraphQL MCP servers effectively.

## Using the MCP Inspector

The built-in MCP Inspector is the easiest way to test your tools interactively:

1. Enable GraphQL HTTP in your server:
```python
server = GraphQLMCP.from_api(api, graphql_http=True)
```

2. Start your server:
```bash
python app.py
```

3. Navigate to `http://localhost:8002` in your browser

4. Use the inspector to:
   - Browse available tools
   - Execute tools with custom parameters
   - Test authentication
   - View responses and errors

## Unit Testing

Test your MCP tools programmatically:

```python
import pytest
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

class TestAPI:
    @field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

def test_mcp_server():
    # Create API and server
    api = GraphQLAPI(root_type=TestAPI())
    server = GraphQLMCP.from_api(api, name="Test")

    # Server should be created successfully
    assert server is not None
    assert server.name == "Test"

def test_tool_execution():
    api = GraphQLAPI(root_type=TestAPI())
    server = GraphQLMCP.from_api(api)

    # Execute GraphQL query
    result = api.execute('{ hello(name: "Tester") }')

    assert result.data == {"hello": "Hello, Tester!"}
    assert result.errors is None
```

## Integration Testing

Test the full HTTP server:

```python
import pytest
from starlette.testclient import TestClient
from graphql_api import GraphQLAPI, field
from graphql_mcp.server import GraphQLMCP

class TestAPI:
    @field
    def hello(self, name: str = "World") -> str:
        return f"Hello, {name}!"

@pytest.fixture
def client():
    api = GraphQLAPI(root_type=TestAPI())
    server = GraphQLMCP.from_api(api, graphql_http=True)
    app = server.http_app(transport="http", stateless_http=True)
    return TestClient(app)

def test_graphql_endpoint(client):
    response = client.post(
        "/graphql",
        json={"query": "{ hello(name: \"Tester\") }"}
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"]["hello"] == "Hello, Tester!"

def test_mcp_endpoint(client):
    # Test MCP protocol endpoint
    response = client.get("/")
    assert response.status_code == 200
```

## Testing with Authentication

Test authenticated endpoints:

```python
import pytest
from starlette.testclient import TestClient
from graphql_mcp.server import GraphQLMCP

@pytest.fixture
def auth_client():
    server = GraphQLMCP.from_remote_url(
        url="https://api.example.com/graphql",
        bearer_token="test_token",
        graphql_http=True
    )
    app = server.http_app()
    return TestClient(app)

def test_authenticated_request(auth_client):
    response = auth_client.post(
        "/graphql",
        json={"query": "{ protectedField }"},
        headers={"Authorization": "Bearer test_token"}
    )

    assert response.status_code == 200
```

## Testing Remote Connections

Test connections to remote GraphQL APIs:

```python
import pytest
from graphql_mcp.server import GraphQLMCP

@pytest.mark.integration
def test_remote_connection():
    # Test connecting to a public API
    server = GraphQLMCP.from_remote_url(
        url="https://countries.trevorblades.com/",
        name="Countries Test"
    )

    assert server is not None
    assert server.name == "Countries Test"

@pytest.mark.integration
def test_remote_query():
    server = GraphQLMCP.from_remote_url(
        url="https://countries.trevorblades.com/"
    )

    # The server should have tools generated from the schema
    # You can test by executing queries through the underlying schema
```

## Mocking Remote APIs

Mock remote GraphQL APIs for testing:

```python
import pytest
from unittest.mock import patch, Mock
from graphql_mcp.server import GraphQLMCP

def test_with_mocked_remote():
    with patch('graphql_mcp.server.fetch_remote_schema') as mock_fetch:
        # Mock the remote schema fetch
        mock_fetch.return_value = Mock()

        server = GraphQLMCP.from_remote_url(
            url="https://fake-api.com/graphql"
        )

        assert mock_fetch.called
```

## Continuous Integration

Example GitHub Actions workflow for testing:

```yaml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4

    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'

    - name: Install dependencies
      run: |
        pip install -e .
        pip install pytest pytest-cov

    - name: Run tests
      run: |
        pytest --cov=graphql_mcp tests/

    - name: Upload coverage
      uses: codecov/codecov-action@v3
```

## Test Coverage

Measure test coverage:

```bash
# Install coverage tools
pip install pytest pytest-cov

# Run tests with coverage
pytest --cov=graphql_mcp --cov-report=html tests/

# View coverage report
open htmlcov/index.html
```

## Best Practices

1. **Test Schema Generation**: Verify tools are generated correctly
2. **Test Type Mapping**: Ensure GraphQL types map to Python correctly
3. **Test Authentication**: Verify auth headers are passed correctly
4. **Test Error Handling**: Check how errors are handled and formatted
5. **Test Edge Cases**: Null values, empty lists, large inputs
6. **Integration Tests**: Test the full HTTP server
7. **Mock External APIs**: Use mocking for external dependencies

## Next Steps

- Explore more [examples](examples/)
- Check out the [API reference](api-reference/)
- Learn about [configuration](configuration/)
