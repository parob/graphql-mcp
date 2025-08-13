"""Tests for Undefined value handling in RemoteGraphQLClient."""

import pytest
from unittest.mock import AsyncMock, patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class TestUndefinedHandling:
    """Test cases for handling Undefined values in variable serialization."""

    @pytest.fixture
    def client(self):
        """Create a test RemoteGraphQLClient."""
        return RemoteGraphQLClient("http://example.com/graphql")

    def test_clean_variables_none_input(self, client):
        """Test that None input returns None."""
        result = client._clean_variables(None)
        assert result is None

    def test_clean_variables_empty_dict(self, client):
        """Test that empty dict returns empty dict."""
        result = client._clean_variables({})
        assert result == {}

    def test_clean_variables_no_undefined(self, client):
        """Test that variables without Undefined values are unchanged."""
        variables = {
            "name": "test",
            "age": 25,
            "active": True,
            "nested": {"key": "value"}
        }
        result = client._clean_variables(variables)
        assert result == variables

    def test_clean_variables_simple_undefined(self, client):
        """Test cleaning simple Undefined values."""
        variables = {
            "name": "test",
            "undefined_field": Undefined,
            "age": 25
        }
        result = client._clean_variables(variables)
        expected = {"name": "test", "undefined_field": None, "age": 25}
        assert result == expected

    def test_clean_variables_nested_undefined(self, client):
        """Test cleaning nested dictionaries with Undefined values."""
        variables = {
            "user": {
                "name": "test",
                "email": Undefined,
                "profile": {
                    "bio": "test bio",
                    "avatar": Undefined
                }
            }
        }
        result = client._clean_variables(variables)
        expected = {
            "user": {
                "name": "test",
                "email": None,
                "profile": {
                    "bio": "test bio",
                    "avatar": None
                }
            }
        }
        assert result == expected

    def test_clean_variables_list_with_undefined(self, client):
        """Test cleaning lists containing Undefined values."""
        variables = {
            "tags": ["tag1", Undefined, "tag2"],
            "ids": [1, 2, Undefined, 3]
        }
        result = client._clean_variables(variables)
        expected = {
            "tags": ["tag1", None, "tag2"],
            "ids": [1, 2, None, 3]
        }
        assert result == expected

    def test_clean_variables_nested_dicts_in_lists(self, client):
        """Test cleaning nested dictionaries within lists."""
        variables = {
            "items": [
                {"name": "item1", "optional": Undefined},
                {"name": "item2", "optional": "value"},
                Undefined,  # This becomes None in the list
                {"name": "item3", "nested": {"keep": "this", "remove": Undefined}}
            ]
        }
        result = client._clean_variables(variables)
        expected = {
            "items": [
                {"name": "item1", "optional": None},
                {"name": "item2", "optional": "value"},
                None,  # Undefined becomes None
                {"name": "item3", "nested": {"keep": "this", "remove": None}}
            ]
        }
        assert result == expected

    def test_clean_variables_empty_after_cleaning(self, client):
        """Test that structures with Undefined values become None values."""
        variables = {
            "empty_dict": {"undefined_only": Undefined},
            "empty_list": [Undefined, Undefined],
            "valid_field": "keep_me"
        }
        result = client._clean_variables(variables)
        expected = {
            "empty_dict": {"undefined_only": None},
            "empty_list": [None, None],
            "valid_field": "keep_me"
        }
        assert result == expected

    def test_clean_variables_all_undefined(self, client):
        """Test that completely Undefined structure becomes all None values."""
        variables = {
            "field1": Undefined,
            "field2": Undefined,
            "nested": {"inner": Undefined}
        }
        result = client._clean_variables(variables)
        expected = {
            "field1": None,
            "field2": None,
            "nested": {"inner": None}
        }
        assert result == expected

    def test_clean_variables_complex_nesting(self, client):
        """Test cleaning deeply nested structures."""
        variables = {
            "level1": {
                "level2": {
                    "level3": {
                        "keep": "this",
                        "remove": Undefined,
                        "list": [Undefined, "item", Undefined]
                    },
                    "other": Undefined
                },
                "sibling": "value"
            }
        }
        result = client._clean_variables(variables)
        expected = {
            "level1": {
                "level2": {
                    "level3": {
                        "keep": "this",
                        "remove": None,
                        "list": [None, "item", None]
                    },
                    "other": None
                },
                "sibling": "value"
            }
        }
        assert result == expected

    @pytest.mark.asyncio
    async def test_execute_request_with_undefined_variables(self, client):
        """Test that _execute_request properly cleans Undefined variables."""
        variables = {
            "name": "test",
            "optional_field": Undefined,
            "nested": {
                "required": "value",
                "optional": Undefined
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"test": "result"}})
        
        # Mock schema introspection to avoid interfering with the test
        with patch.object(client, '_introspect_schema', new_callable=AsyncMock):
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
                
                result = await client._execute_request(
                    "query Test($name: String, $nested: TestInput) { test }",
                    variables,
                    None,
                    False,
                    {}
                )

                # Verify that the request was made with cleaned variables
                call_args = mock_post.call_args
                sent_payload = call_args[1]['json']
                
                expected_variables = {
                    "name": "test",
                    "optional_field": None,
                    "nested": {"required": "value", "optional": None}
                }
                assert sent_payload['variables'] == expected_variables
                assert result == {"test": "result"}

    @pytest.mark.asyncio
    async def test_execute_with_token_cleans_variables(self, client):
        """Test that execute_with_token passes variables to _execute_request correctly."""
        variables = {"field": Undefined}
        
        with patch.object(client, '_execute_request', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"data": "test"}
            
            await client.execute_with_token("query", variables)
            
            # Variables are passed as-is to _execute_request, cleaning happens there
            mock_execute.assert_called_once_with(
                "query", variables, None, True, client.headers
            )

    @pytest.mark.asyncio
    async def test_execute_cleans_variables(self, client):
        """Test that execute method passes variables to _execute_request correctly."""
        variables = {"valid": "keep", "invalid": Undefined}
        
        with patch.object(client, '_execute_request', new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"data": "test"}
            
            await client.execute("query", variables)
            
            # Variables are passed as-is to _execute_request, cleaning happens there
            mock_execute.assert_called_once_with(
                "query", variables, None, True, client.headers
            )

    def test_remove_unused_variables_from_query_no_variables(self, client):
        """Test removing variable declarations when no variables provided."""
        query = "query GetUser($id: ID!, $name: String) { user(id: $id, name: $name) { id name } }"
        result = client._remove_unused_variables_from_query(query, None)
        expected = "query GetUser { user(id: $id, name: $name) { id name } }"
        assert result == expected

    def test_remove_unused_variables_from_query_partial_variables(self, client):
        """Test removing only unused variable declarations."""
        query = "query GetUser($id: ID!, $name: String, $age: Int) { user { id } }"
        variables = {"id": "123", "age": 25}  # name not provided
        result = client._remove_unused_variables_from_query(query, variables)
        expected = "query GetUser($id: ID!, $age: Int) { user { id } }"
        assert result == expected

    def test_remove_unused_variables_from_query_all_variables_present(self, client):
        """Test query remains unchanged when all variables are present."""
        query = "query GetUser($id: ID!, $name: String) { user(id: $id) { name } }"
        variables = {"id": "123", "name": "John"}
        result = client._remove_unused_variables_from_query(query, variables)
        assert result == query

    def test_transform_null_arrays_simple(self, client):
        """Test transforming null values to empty arrays for array-like field names."""
        data = {
            "users": None,  # Should become []
            "items": None,  # Should become []
            "name": None,   # Should remain None
            "count": None   # Should remain None
        }
        result = client._transform_null_arrays(data)
        expected = {
            "users": [],
            "items": [],
            "name": None,
            "count": None
        }
        assert result == expected

    def test_transform_null_arrays_nested(self, client):
        """Test transforming null arrays in nested structures."""
        data = {
            "user": {
                "name": "John",
                "addresses": None,  # Should become []
                "profile": {
                    "tags": None,    # Should become []
                    "bio": None      # Should remain None
                }
            },
            "results": None  # Should become []
        }
        result = client._transform_null_arrays(data)
        expected = {
            "user": {
                "name": "John",
                "addresses": [],
                "profile": {
                    "tags": [],
                    "bio": None
                }
            },
            "results": []
        }
        assert result == expected

    def test_transform_null_arrays_in_lists(self, client):
        """Test transforming null arrays within lists."""
        data = {
            "data": [
                {"items": None, "name": "test1"},
                {"items": ["a", "b"], "name": "test2"},
                {"components": None, "name": "test3"}
            ]
        }
        result = client._transform_null_arrays(data)
        expected = {
            "data": [
                {"items": [], "name": "test1"},
                {"items": ["a", "b"], "name": "test2"},
                {"components": [], "name": "test3"}
            ]
        }
        assert result == expected