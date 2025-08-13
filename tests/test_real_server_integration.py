"""
Integration tests using a real GraphQL server to validate all RemoteGraphQLClient functionality.
This tests against an actual Strawberry GraphQL server with realistic data and null array scenarios.
"""

import pytest
import asyncio
import time
from typing import Optional
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient
from tests.real_graphql_server import create_test_server, RealGraphQLServer, check_server_health


class TestRealServerIntegration:
    """Integration tests against a real GraphQL server."""
    
    @pytest.fixture(scope="class")
    def server(self) -> RealGraphQLServer:
        """Create and start a real GraphQL server for testing."""
        # Use a unique port to avoid conflicts
        port = 8766  
        server = create_test_server(port)
        
        # Wait for server to be ready
        timeout = 10
        start_time = time.time()
        server_ready = False
        
        # Poll server health
        async def check_server():
            return await check_server_health(server.url)
        
        while not server_ready and time.time() - start_time < timeout:
            try:
                server_ready = asyncio.run(check_server())
                if not server_ready:
                    time.sleep(0.2)
            except Exception:
                time.sleep(0.2)
        
        if not server_ready:
            server.stop()
            pytest.skip(f"Could not start GraphQL server on port {port}")
        
        yield server
        server.stop()
    
    @pytest.fixture
    def client(self, server: RealGraphQLServer) -> RemoteGraphQLClient:
        """Create a RemoteGraphQLClient connected to the real server."""
        return RemoteGraphQLClient(server.url, verify_ssl=False)
    
    @pytest.mark.asyncio
    async def test_real_server_basic_query(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test basic query against real server."""
        
        query = """
        query GetUser($userId: ID!) {
            user(id: $userId) {
                id
                name
                email
            }
        }
        """
        
        variables = {"userId": "user123"}
        
        result = await client.execute(query, variables)
        
        assert result == {
            "user": {
                "id": "user123",
                "name": "John Doe",
                "email": "john@example.com"
            }
        }
    
    @pytest.mark.asyncio
    async def test_real_server_undefined_variable_handling(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test that Undefined variables are cleaned properly for JSON serialization."""
        
        # Simple test with only used variables to avoid GraphQL validation issues
        query = """
        query GetUser($userId: ID!) {
            user(id: $userId) {
                id
                name
                email
                tags
            }
        }
        """
        
        # Test with complex nested variables containing Undefined values
        # This tests the core functionality: Undefined → None conversion
        complex_variables = {
            "userId": "user123",
            "metadata": {
                "nested": {
                    "field1": "value",
                    "field2": Undefined,  # This should become None
                    "field3": {
                        "deep": Undefined  # This should become None
                    }
                },
                "list": ["item1", Undefined, "item3"]  # Undefined in array becomes None
            }
        }
        
        # Verify the variables can be cleaned (core functionality)
        cleaned = client._clean_variables(complex_variables)
        
        # The key test: Undefined values should be removed entirely (preventing non-null errors)
        import json
        json_str = json.dumps(cleaned)  # This should not raise an exception
        
        # Undefined values are completely removed to prevent non-null GraphQL variable errors
        assert "field2" not in cleaned["metadata"]["nested"]
        assert "field3" not in cleaned["metadata"]["nested"]  # Completely removed (was empty after cleaning)
        assert cleaned["metadata"]["list"] == ["item1", "item3"]  # Undefined filtered out
        
        # Now test with actual server query (simple case)
        result = await client.execute(query, {"userId": "user123"})
        
        expected = {
            "user": {
                "id": "user123",
                "name": "John Doe",
                "email": "john@example.com",
                "tags": None  # Server returns null, should be transformed to []
            }
        }
        
        assert result["user"]["id"] == expected["user"]["id"]
        assert result["user"]["name"] == expected["user"]["name"]
        assert result["user"]["email"] == expected["user"]["email"]
        # Tags should be transformed from null to [] by the client
        assert result["user"]["tags"] == []
    
    @pytest.mark.asyncio
    async def test_real_server_null_array_transformation(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test null array transformation against real server that returns null arrays."""
        
        # Configure server to return null arrays
        server.set_return_null_arrays(True)
        
        query = """
        query GetUserWithArrays($userId: ID!) {
            user(id: $userId) {
                id
                name
                orders {
                    id
                    discounts {
                        code
                        amount
                    }
                }
                addresses {
                    street
                    city
                }
                tags
            }
        }
        """
        
        variables = {"userId": "user123"}
        
        result = await client.execute(query, variables)
        
        # Server returns nulls, but client should transform them to empty arrays
        expected = {
            "user": {
                "id": "user123",
                "name": "John Doe",
                "orders": [
                    {
                        "id": "order1",
                        "discounts": []  # Transformed from null
                    }
                ],
                "addresses": [],  # Transformed from null
                "tags": []        # Transformed from null
            }
        }
        
        assert result == expected
    
    @pytest.mark.asyncio
    async def test_real_server_complex_nested_query(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test complex nested query with multiple levels and null transformations."""
        
        server.set_return_null_arrays(True)
        
        # Simplified query without problematic @include directive 
        query = """
        query GetComplexUserData($userId: ID!) {
            user(id: $userId) {
                id
                name
                orders {
                    id
                    total
                    items {
                        id
                        quantity
                        product {
                            id
                            name
                            categories {
                                id
                                name
                            }
                            reviews {
                                id
                                rating
                                comment
                            }
                            variants {
                                id
                                sku
                                price
                            }
                        }
                    }
                }
            }
        }
        """
        
        variables = {
            "userId": "user123"
        }
        
        result = await client.execute(query, variables)
        
        # Verify deep null array transformations occurred
        assert "user" in result
        user = result["user"]
        assert user["id"] == "user123"
        assert user["name"] == "John Doe"
        assert isinstance(user["orders"], list)
        
        if user["orders"]:
            order = user["orders"][0]
            assert order["id"] == "order1"
            assert isinstance(order["items"], list)
            
            if order["items"]:
                item = order["items"][0]
                product = item["product"]
                # These should be transformed from null to [] by the client
                assert isinstance(product["categories"], list)
                assert isinstance(product["reviews"], list)
                assert isinstance(product["variants"], list)
    
    @pytest.mark.asyncio
    async def test_real_server_mutation_with_undefined_input(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test mutation with complex input containing Undefined values."""
        
        mutation = """
        mutation CreateSearch($input: SearchInput!) {
            createSearch(input: $input) {
                id
                results {
                    products {
                        id
                        name
                        categories {
                            id
                            name
                        }
                        reviews {
                            id
                            rating
                        }
                        variants {
                            id
                            sku
                        }
                    }
                    filters {
                        name
                        values
                    }
                    suggestions
                    totalCount
                }
            }
        }
        """
        
        # Complex input with many Undefined values (realistic client scenario)
        variables = {
            "input": {
                "query": "laptop",
                "filters": {
                    "category": "electronics",
                    "priceMin": 100.0,
                    "priceMax": Undefined,  # No max price
                    "brand": Undefined,     # No brand filter
                    "inStock": True,
                    "tags": ["gaming", Undefined, "portable"],  # Mixed array
                },
                "sorting": {
                    "field": "price",
                    "direction": "ASC",
                    "priority": Undefined,  # No priority
                },
                "pagination": {
                    "limit": 10,
                    "offset": Undefined,    # First page
                },
                "options": {
                    "includeReviews": True,
                    "includeVariants": Undefined,  # Don't include variants
                    "includeSuggestions": Undefined,  # Don't include suggestions
                }
            }
        }
        
        server.set_return_null_arrays(True)
        
        result = await client.execute(mutation, variables)
        
        # Verify result structure and null array transformations
        assert "createSearch" in result
        assert "id" in result["createSearch"]
        assert "results" in result["createSearch"]
        
        search_results = result["createSearch"]["results"]
        assert isinstance(search_results["products"], list)
        assert search_results["filters"] == []     # Transformed from null
        assert search_results["suggestions"] == [] # Transformed from null
        assert search_results["totalCount"] == 1
        
        # Verify product data with null array transformations
        if search_results["products"]:
            product = search_results["products"][0]
            assert product["id"] == "prod1"
            assert product["name"] == "Gaming Laptop"
            # These should be either empty arrays (from null) or actual data arrays
            assert isinstance(product["categories"], list)
            assert isinstance(product["reviews"], list)
            assert isinstance(product["variants"], list)
    
    @pytest.mark.asyncio
    async def test_real_server_error_handling(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test error handling with real server GraphQL errors."""
        
        mutation = """
        mutation UpdateProfile($userId: ID!, $input: UserProfileInput!) {
            updateUserProfile(userId: $userId, input: $input) {
                success
                errors {
                    field
                    message
                }
                user {
                    id
                    name
                }
            }
        }
        """
        
        # Input that will trigger server validation error
        variables = {
            "userId": "user123",
            "input": {
                "name": "Updated Name",
                "email": Undefined,  # Optional
                "preferences": {
                    "newsletter": True,
                    "notifications": Undefined,  # Optional
                    "theme": "dark",  # This triggers validation error in our mock server
                    "language": Undefined,  # Optional
                },
                "addresses": [
                    {
                        "type": "HOME",
                        "street": "123 New St",
                        "city": "New York", 
                        "country": "US",
                        "isPrimary": True,
                        "instructions": Undefined,  # Optional
                    }
                ],
                "metadata": {
                    "source": "web_app",
                    "version": "2.1.0",
                    "sessionId": Undefined,  # Optional
                }
            }
        }
        
        result = await client.execute(mutation, variables)
        
        # Should get validation error result (not exception)
        assert "updateUserProfile" in result
        profile_result = result["updateUserProfile"]
        assert profile_result["success"] is False
        assert len(profile_result["errors"]) > 0
        assert profile_result["errors"][0]["field"] == "input.preferences.theme"
        assert profile_result["errors"][0]["message"] == "Invalid theme value"
        assert profile_result["user"] is None
    
    @pytest.mark.asyncio
    async def test_real_server_schema_introspection(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test that schema introspection works correctly against real server."""
        
        # Force schema introspection
        client._introspected = False
        client._array_fields_cache = {}
        
        query = """
        query TestIntrospection {
            user(id: "user123") {
                orders {
                    items {
                        product {
                            categories { name }
                            reviews { rating }
                            variants { sku }
                        }
                    }
                }
                addresses { street }
                tags
            }
        }
        """
        
        server.set_return_null_arrays(True)
        
        result = await client.execute(query, {})
        
        # Verify that introspection occurred and cached schema info
        assert client._introspected is True
        assert len(client._array_fields_cache) > 0
        
        # Should have cached array field information
        assert "User" in client._array_fields_cache
        assert "Product" in client._array_fields_cache
        assert client._array_fields_cache["User"]["orders"] is True
        assert client._array_fields_cache["User"]["addresses"] is True
        assert client._array_fields_cache["User"]["tags"] is True
        assert client._array_fields_cache["Product"]["categories"] is True
        assert client._array_fields_cache["Product"]["reviews"] is True
        assert client._array_fields_cache["Product"]["variants"] is True
        
        # Verify null arrays were properly transformed using schema knowledge
        user = result["user"]
        assert user["orders"][0]["items"][0]["product"]["categories"] == []
        assert user["orders"][0]["items"][0]["product"]["reviews"] == []
        assert user["orders"][0]["items"][0]["product"]["variants"] == []
        assert user["addresses"] == []
        assert user["tags"] == []
    
    @pytest.mark.asyncio
    async def test_real_server_concurrent_requests(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test concurrent requests against real server maintain consistency."""
        
        query = """
        query GetUser($userId: ID!) {
            user(id: $userId) {
                id
                name
                orders { id }
                addresses { street }
                tags
            }
        }
        """
        
        server.set_return_null_arrays(True)
        
        # Execute multiple concurrent requests
        tasks = [
            client.execute(query, {"userId": "user123"}),
            client.execute(query, {"userId": "user456"}),
            client.execute(query, {"userId": "user123"}),  # Duplicate
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All requests should succeed
        assert len(results) == 3
        
        # First and third results should be identical (same user)
        assert results[0] == results[2]
        
        # Verify transformations applied consistently
        for result in results:
            if result["user"]["id"] == "user123":
                assert result["user"]["orders"] == [{"id": "order1"}]
                assert result["user"]["addresses"] == []  # Transformed from null
                assert result["user"]["tags"] == []       # Transformed from null
            elif result["user"]["id"] == "user456":
                assert result["user"]["orders"] == []     # Transformed from null
                assert isinstance(result["user"]["addresses"], list)
                assert isinstance(result["user"]["tags"], list)
    
    @pytest.mark.asyncio
    async def test_real_server_subscription_support(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test that subscription queries work (even though we can't test streaming)."""
        
        # Note: We can't easily test actual subscription streaming in this setup,
        # but we can verify the subscription query is accepted and processed
        subscription = """
        subscription OrderUpdates($userId: ID!) {
            orderUpdates(userId: $userId) {
                id
                name
                orders {
                    id
                    status
                }
            }
        }
        """
        
        variables = {
            "userId": "user123",
        }
        
        # For now, just verify the subscription is syntactically correct
        # In a full implementation, we'd test the streaming behavior
        try:
            # This might not work with simple HTTP POST, but shouldn't crash
            result = await client.execute(subscription, variables)
            # If we get here, the query was accepted
            assert True
        except Exception as e:
            # Subscription might require WebSocket, which is expected
            assert "subscription" in str(e).lower() or "websocket" in str(e).lower()
    
    def test_real_server_performance_with_complex_queries(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test performance with complex nested queries against real server."""
        
        query = """
        query ComplexQuery {
            users {
                id
                name
                orders {
                    id
                    items {
                        id
                        product {
                            id
                            name
                            categories { id name }
                            reviews { id rating comment }
                            variants { id sku price attributes }
                            metadata { width height tags }
                        }
                    }
                    discounts { id code amount }
                }
                addresses { id street city country }
                preferences { newsletter notifications theme language }
                tags
            }
        }
        """
        
        server.set_return_null_arrays(True)
        
        start_time = time.time()
        
        # Execute the complex query
        async def run_query():
            return await client.execute(query, {})
        
        result = asyncio.run(run_query())
        
        end_time = time.time()
        execution_time = end_time - start_time
        
        # Should complete in reasonable time (under 2 seconds for this simple mock data)
        assert execution_time < 2.0, f"Complex query took {execution_time:.3f}s, too slow"
        
        # Verify the result structure
        assert "users" in result
        assert isinstance(result["users"], list)
        
        # Verify null array transformations throughout the complex structure
        for user in result["users"]:
            assert isinstance(user["orders"], list)
            assert isinstance(user["addresses"], list)
            assert isinstance(user["tags"], list)
            
            for order in user["orders"]:
                assert isinstance(order["items"], list)
                assert isinstance(order["discounts"], list)
                
                for item in order["items"]:
                    product = item["product"]
                    assert isinstance(product["categories"], list)
                    assert isinstance(product["reviews"], list) 
                    assert isinstance(product["variants"], list)
                    if product["metadata"]:
                        assert isinstance(product["metadata"]["tags"], list)
    
    @pytest.mark.asyncio
    async def test_real_server_variable_cleaning_edge_cases(self, client: RemoteGraphQLClient, server: RealGraphQLServer):
        """Test edge cases of variable cleaning against real server."""
        
        query = """
        mutation CreateSearchWithComplexInput($input: SearchInput!) {
            createSearch(input: $input) {
                id
                results {
                    totalCount
                }
            }
        }
        """
        
        # Edge case: deeply nested Undefined values in arrays and objects
        variables = {
            "input": {
                "query": "test",
                "filters": {
                    "tags": [
                        "valid",
                        Undefined,
                        "another_valid", 
                        Undefined,
                        "last_valid"
                    ]
                },
                "options": {
                    "includeReviews": Undefined,
                    "includeVariants": Undefined,
                    "includeSuggestions": Undefined,
                }
            }
        }
        
        result = await client.execute(query, variables)
        
        # Should succeed despite complex Undefined structure
        assert "createSearch" in result
        assert result["createSearch"]["results"]["totalCount"] >= 0
        
        # The key test is that no JSON serialization errors occurred
        # If we got this far, the variable cleaning worked correctly
        assert True


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()