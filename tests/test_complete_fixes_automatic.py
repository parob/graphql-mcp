"""Integration tests for automatic schema deduction in complete workflows."""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class TestCompleteFixesAutomatic:
    """Test complete workflows with automatic schema deduction."""

    @pytest.fixture
    def client(self):
        return RemoteGraphQLClient("http://example.com/graphql")

    def test_undefined_variable_cleaning(self, client):
        """Test automatic Undefined variable cleaning."""
        variables = {
            "name": "test",
            "email": Undefined,
            "tags": ["tag1", Undefined, "tag2"]
        }
        result = client._clean_variables(variables)
        expected = {
            "name": "test",
            # email removed (was Undefined)
            "tags": ["tag1", "tag2"]  # Undefined filtered out
        }
        assert result == expected

    def test_query_variable_cleaning(self, client):
        """Test automatic query variable declaration cleaning."""
        query = "query GetData($id: ID!, $name: String, $age: Int) { user }"
        variables = {"id": "123", "age": 25}  # name not provided
        
        cleaned_query = client._remove_unused_variables_from_query(query, variables)
        expected = "query GetData($id: ID!, $age: Int) { user }"
        
        assert cleaned_query == expected

    def test_automatic_null_array_transformation(self, client):
        """Test automatic null-to-array transformation with schema."""
        
        # Mock schema with automatic introspection
        mock_schema = {
            "__schema": {
                "types": [
                    {
                        "name": "Query",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "users", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "User"}}},
                            {"name": "user", "type": {"kind": "OBJECT", "name": "User"}},
                            {"name": "totalCount", "type": {"kind": "SCALAR", "name": "Int"}}
                        ]
                    },
                    {
                        "name": "User",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "name", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "tags", "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}}}
                        ]
                    }
                ]
            }
        }
        
        with patch.object(client, '_raw_execute_request', return_value=mock_schema):
            asyncio.run(client._introspect_schema())
        
        data = {
            "users": None,      # Should become [] (LIST in schema)
            "totalCount": None, # Should stay None (SCALAR in schema)  
            "user": {
                "name": None,   # Should stay None (SCALAR in schema)
                "tags": None    # Should become [] (LIST in schema)
            }
        }
        
        result = client._transform_null_arrays(data, type_context="Query")
        expected = {
            "users": [],        # Automatically converted
            "totalCount": None, # Not converted
            "user": {
                "name": None,   # Not converted
                "tags": []      # Automatically converted
            }
        }
        
        assert result == expected

    @pytest.mark.asyncio
    async def test_end_to_end_automatic_workflow(self, client):
        """Test complete end-to-end workflow with automatic schema deduction."""
        
        # Mock complete schema
        mock_schema = {
            "__schema": {
                "types": [
                    {
                        "name": "Mutation",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "createUser", "type": {"kind": "OBJECT", "name": "User"}}
                        ]
                    },
                    {
                        "name": "User",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "id", "type": {"kind": "SCALAR", "name": "ID"}},
                            {"name": "name", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "tags", "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}}}
                        ]
                    }
                ]
            }
        }
        
        # Variables with Undefined
        variables = {
            "name": "John Doe",
            "email": Undefined,  # Will be removed
            "tags": ["dev", Undefined, "python"]  # Undefined filtered
        }
        
        # Mock response with nulls
        mock_response_data = {
            "data": {
                "createUser": {
                    "id": "123",
                    "name": "John Doe",
                    "tags": None  # Should become []
                }
            }
        }
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        
        with patch.object(client, '_raw_execute_request', return_value=mock_schema):
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
                
                result = await client.execute(
                    "mutation CreateUser($name: String!, $email: String) { createUser { id name tags } }",
                    variables
                )
                
                # Verify Undefined cleaning worked
                call_args = mock_post.call_args
                sent_payload = call_args[1]['json']
                assert "email" not in sent_payload['variables']
                assert sent_payload['variables']['tags'] == ["dev", "python"]
                
                # Verify automatic transformation worked
                expected_result = {
                    "createUser": {
                        "id": "123",
                        "name": "John Doe", 
                        "tags": []  # Automatically converted from null
                    }
                }
                
                assert result == expected_result