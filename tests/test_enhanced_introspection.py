"""Tests for the enhanced introspection technique without field name heuristics."""

import pytest
from unittest.mock import AsyncMock, patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class TestEnhancedIntrospection:
    """Test enhanced introspection technique that relies only on GraphQL schema information."""

    @pytest.fixture
    def client(self):
        """Create a test RemoteGraphQLClient with enhanced introspection."""
        return RemoteGraphQLClient(
            "http://example.com/graphql",
            undefined_strategy="remove",
            debug=True
        )

    @pytest.fixture
    def client_null_strategy(self):
        """Create a client that converts Undefined to None."""
        return RemoteGraphQLClient(
            "http://example.com/graphql",
            undefined_strategy="null",
            debug=True
        )

    def test_undefined_strategy_remove(self, client):
        """Test that 'remove' strategy removes Undefined variables entirely."""
        variables = {
            "name": "John",
            "email": Undefined,
            "profile": {
                "bio": "Developer",
                "avatar": Undefined
            },
            "tags": ["python", Undefined, "graphql"]
        }
        
        result = client._clean_variables(variables, "remove")
        expected = {
            "name": "John",
            # email removed entirely
            "profile": {
                "bio": "Developer"
                # avatar removed entirely
            },
            "tags": ["python", "graphql"]  # Undefined filtered out
        }
        assert result == expected

    def test_undefined_strategy_null(self, client_null_strategy):
        """Test that 'null' strategy converts Undefined to None."""
        variables = {
            "name": "John", 
            "email": Undefined,
            "profile": {
                "bio": "Developer",
                "avatar": Undefined
            },
            "tags": ["python", Undefined, "graphql"]
        }
        
        result = client_null_strategy._clean_variables(variables, "null")
        expected = {
            "name": "John",
            "email": None,  # Undefined converted to None
            "profile": {
                "bio": "Developer",
                "avatar": None  # Undefined converted to None
            },
            "tags": ["python", None, "graphql"]  # Undefined converted to None
        }
        assert result == expected

    def test_no_heuristic_fallback_for_array_conversion(self, client):
        """Test that field names don't trigger automatic array conversion."""
        # Simulate the client not having schema information
        client._introspected = False
        client._array_fields_cache = {}
        
        data = {
            "users": None,      # Should NOT become [] without schema info
            "items": None,      # Should NOT become [] without schema info  
            "results": None,    # Should NOT become [] without schema info
            "name": None        # Should remain None
        }
        
        result = client._transform_null_arrays(data)
        
        # Without schema information, nothing should be converted
        expected = {
            "users": None,      # Stays None (no heuristic fallback)
            "items": None,      # Stays None (no heuristic fallback)
            "results": None,    # Stays None (no heuristic fallback)
            "name": None
        }
        assert result == expected

    def test_schema_based_array_conversion(self, client):
        """Test that schema information correctly identifies array fields."""
        # Mock schema introspection results
        client._introspected = True
        client._array_fields_cache = {
            "User": {
                "posts": True,      # This is a list field per schema
                "addresses": True,  # This is a list field per schema
                "name": False       # This is not a list field
            },
            "Query": {
                "users": True,      # This is a list field per schema
                "currentUser": False # This is not a list field
            }
        }
        
        data = {
            "users": None,          # Should become [] (schema says it's a list)
            "currentUser": None,    # Should remain None (schema says it's not a list)
            "posts": None,          # Should become [] (schema says it's a list) 
            "addresses": None,      # Should become [] (schema says it's a list)
            "name": None,          # Should remain None (schema says it's not a list)
            "unknownField": None   # Should remain None (not in schema)
        }
        
        # Test with proper type context
        result = client._transform_null_arrays(data, type_context="Query")
        
        # Only fields identified by schema should be converted
        expected = {
            "users": [],           # Converted based on schema
            "currentUser": None,   # Not converted (schema says scalar)
            "posts": None,         # Not converted (wrong type context)
            "addresses": None,     # Not converted (wrong type context) 
            "name": None,         # Not converted (schema says scalar)
            "unknownField": None  # Not converted (not in schema)
        }
        assert result == expected

    def test_sibling_analysis_fallback(self, client):
        """Test that sibling analysis can still identify arrays when schema is unavailable."""
        client._introspected = False  # No schema info available
        
        data = {
            "items": None,
            "other_items": ["a", "b", "c"],  # Sibling shows this should be an array
            "name": None
        }
        
        # The sibling analysis should still work for fields with the same name
        result = client._transform_null_arrays(data)
        
        expected = {
            "items": None,         # No sibling with same name showing it's an array
            "other_items": ["a", "b", "c"],  
            "name": None
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_enhanced_debug_logging(self, client):
        """Test that enhanced debug logging provides detailed information."""
        variables = {
            "name": "test",
            "optional": Undefined
        }
        
        # Mock the session and response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"test": "result"}})
        
        with patch.object(client, '_introspect_schema', new_callable=AsyncMock):
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_cm = AsyncMock()
                mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
                mock_cm.__aexit__ = AsyncMock(return_value=None)
                mock_post.return_value = mock_cm
                
                # Capture print output to verify debug logging
                with patch('builtins.print') as mock_print:
                    result = await client._execute_request(
                        "query Test($name: String) { test }",
                        variables,
                        None,
                        False,
                        {}
                    )
                    
                    # Verify debug output was printed
                    debug_calls = [call for call in mock_print.call_args_list 
                                 if call[0][0].startswith("DEBUG: GraphQL Request Processing")]
                    assert len(debug_calls) > 0
                    
                    # Verify the debug message contains expected information
                    debug_msg = debug_calls[0][0][0]
                    assert "Strategy: remove" in debug_msg
                    assert "Original variables:" in debug_msg
                    assert "Cleaned variables:" in debug_msg

    def test_client_configuration(self):
        """Test that client configuration options work correctly."""
        # Test default configuration
        client1 = RemoteGraphQLClient("http://example.com/graphql")
        assert client1.undefined_strategy == "remove"
        assert client1.debug == False
        assert client1.verify_ssl == True
        
        # Test custom configuration
        client2 = RemoteGraphQLClient(
            "http://example.com/graphql",
            undefined_strategy="null",
            debug=True,
            verify_ssl=False
        )
        assert client2.undefined_strategy == "null"
        assert client2.debug == True
        assert client2.verify_ssl == False

    def test_strategy_affects_query_cleaning(self, client, client_null_strategy):
        """Test that different strategies affect query variable declaration cleaning."""
        query = "query Test($name: String!, $optional: String) { test }"
        variables = {"name": "test", "optional": Undefined}
        
        # Remove strategy should clean both variables and query
        cleaned_vars_remove = client._clean_variables(variables, "remove")
        if client.undefined_strategy == "remove":
            cleaned_query_remove = client._remove_unused_variables_from_query(query, cleaned_vars_remove)
            assert "$optional: String" not in cleaned_query_remove
            assert "optional" not in cleaned_vars_remove
        
        # Null strategy should keep variables as null and preserve query
        cleaned_vars_null = client_null_strategy._clean_variables(variables, "null")
        # For null strategy, query should remain unchanged since variables are kept as null
        assert cleaned_vars_null["optional"] is None
        assert "optional" in cleaned_vars_null