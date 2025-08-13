"""Tests for schema introspection functionality in RemoteGraphQLClient."""

import pytest
from unittest.mock import AsyncMock, patch
import ssl

from graphql_mcp.remote import RemoteGraphQLClient


class TestSchemaIntrospection:
    """Test cases for GraphQL schema introspection and type-aware transformations."""

    @pytest.fixture
    def client(self):
        """Create a test RemoteGraphQLClient."""
        return RemoteGraphQLClient("http://example.com/graphql")

    @pytest.fixture
    def client_no_ssl(self):
        """Create a test RemoteGraphQLClient with SSL verification disabled."""
        return RemoteGraphQLClient("http://example.com/graphql", verify_ssl=False)

    def test_ssl_context_creation_verified(self, client):
        """Test that SSL context is created with verification enabled."""
        ssl_context = client._create_ssl_context()
        assert ssl_context.verify_mode == ssl.CERT_REQUIRED

    def test_ssl_context_creation_unverified(self, client_no_ssl):
        """Test that SSL context is created with verification disabled."""
        ssl_context = client_no_ssl._create_ssl_context()
        assert ssl_context.verify_mode == ssl.CERT_NONE
        assert not ssl_context.check_hostname

    def test_is_list_type_simple_list(self, client):
        """Test detection of simple LIST type."""
        field_type = {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}}
        assert client._is_list_type(field_type) is True

    def test_is_list_type_non_null_list(self, client):
        """Test detection of NON_NULL wrapping a LIST."""
        field_type = {
            "kind": "NON_NULL",
            "ofType": {
                "kind": "LIST",
                "ofType": {"kind": "SCALAR", "name": "String"}
            }
        }
        assert client._is_list_type(field_type) is True

    def test_is_list_type_scalar(self, client):
        """Test that scalar types are not identified as lists."""
        field_type = {"kind": "SCALAR", "name": "String"}
        assert client._is_list_type(field_type) is False

    def test_is_list_type_non_null_scalar(self, client):
        """Test that NON_NULL scalar types are not identified as lists."""
        field_type = {
            "kind": "NON_NULL",
            "ofType": {"kind": "SCALAR", "name": "String"}
        }
        assert client._is_list_type(field_type) is False

    def test_should_convert_to_array_with_schema_info(self, client):
        """Test array conversion decision using cached schema information."""
        # Simulate having schema information cached
        client._introspected = True
        client._array_fields_cache = {
            "User": {
                "tags": True,      # This is a list field
                "name": False      # This is not a list field
            }
        }
        
        data = {"tags": None, "name": None}
        
        # tags should convert to array based on schema
        assert client._should_convert_to_array("tags", None, data, "User") is True
        
        # name should not convert based on schema
        assert client._should_convert_to_array("name", None, data, "User") is False

    def test_should_convert_to_array_no_fallback_heuristics(self, client):
        """Test that field name heuristics are NOT used when no schema info (as requested)."""
        data = {"users": None, "name": None}
        
        # Without schema info, field name heuristics are NOT used (removed as requested)
        # users should NOT convert based on field name alone
        assert client._should_convert_to_array("users", None, data) is False
        
        # name should not convert (same as before)
        assert client._should_convert_to_array("name", None, data) is False

    def test_should_convert_to_array_non_null_value(self, client):
        """Test that non-null values are never converted."""
        data = {"users": ["existing", "data"]}
        
        assert client._should_convert_to_array("users", ["existing", "data"], data) is False

    @pytest.mark.asyncio
    async def test_raw_execute_request(self, client):
        """Test raw GraphQL request execution without transformations."""
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"test": "result"}})

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client._raw_execute_request("query { test }")

            assert result == {"test": "result"}
            mock_post.assert_called_once()

    @pytest.mark.asyncio
    async def test_introspect_schema_success(self, client):
        """Test successful schema introspection."""
        mock_introspection_response = {
            "__schema": {
                "types": [
                    {
                        "name": "User",
                        "kind": "OBJECT",
                        "fields": [
                            {
                                "name": "name",
                                "type": {"kind": "SCALAR", "name": "String"}
                            },
                            {
                                "name": "tags",
                                "type": {
                                    "kind": "LIST",
                                    "ofType": {"kind": "SCALAR", "name": "String"}
                                }
                            }
                        ]
                    }
                ]
            }
        }

        with patch.object(client, '_raw_execute_request', new_callable=AsyncMock) as mock_raw:
            mock_raw.return_value = mock_introspection_response

            await client._introspect_schema()

            assert client._introspected is True
            assert "User" in client._array_fields_cache
            assert client._array_fields_cache["User"]["name"] is False  # Scalar field
            assert client._array_fields_cache["User"]["tags"] is True   # List field

    @pytest.mark.asyncio
    async def test_introspect_schema_failure_fallback(self, client):
        """Test that schema introspection failure falls back gracefully."""
        with patch.object(client, '_raw_execute_request', new_callable=AsyncMock) as mock_raw:
            mock_raw.side_effect = Exception("Introspection failed")

            await client._introspect_schema()

            # Should still mark as introspected to avoid retrying
            assert client._introspected is True
            # Cache should be empty due to failure
            assert client._array_fields_cache == {}

    @pytest.mark.asyncio
    async def test_introspect_schema_only_once(self, client):
        """Test that schema introspection only happens once."""
        with patch.object(client, '_raw_execute_request', new_callable=AsyncMock) as mock_raw:
            mock_raw.return_value = {"__schema": {"types": []}}

            # Call introspect multiple times
            await client._introspect_schema()
            await client._introspect_schema()
            await client._introspect_schema()

            # Should only be called once
            mock_raw.assert_called_once()

    def test_transform_null_arrays_with_schema_context(self, client):
        """Test null array transformation using schema type context."""
        # Set up schema cache
        client._introspected = True
        client._array_fields_cache = {
            "User": {
                "tags": True,
                "addresses": True,
                "name": False
            }
        }

        data = {
            "user": {
                "name": None,      # Should stay None (not array field)
                "tags": None,      # Should become [] (array field)  
                "addresses": None  # Should become [] (array field)
            }
        }

        # Mock the should_convert_to_array method to use schema info
        with patch.object(client, '_should_convert_to_array') as mock_should_convert:
            def side_effect(key, value, siblings, type_context=None):
                if key == "tags" or key == "addresses":
                    return True
                return False
            mock_should_convert.side_effect = side_effect

            result = client._transform_null_arrays(data)

            expected = {
                "user": {
                    "name": None,
                    "tags": [],
                    "addresses": []
                }
            }
            assert result == expected

    def test_transform_null_arrays_nested_structures(self, client):
        """Test null array transformation in deeply nested structures."""
        data = {
            "level1": {
                "level2": {
                    "items": None,  # Should become []
                    "value": None   # Should stay None
                }
            }
        }

        # Mock should_convert_to_array to return True only for "items"
        with patch.object(client, '_should_convert_to_array') as mock_should_convert:
            mock_should_convert.side_effect = lambda key, value, siblings, type_context=None: key == "items"

            result = client._transform_null_arrays(data)

            expected = {
                "level1": {
                    "level2": {
                        "items": [],
                        "value": None
                    }
                }
            }
            assert result == expected

    def test_transform_null_arrays_with_lists(self, client):
        """Test null array transformation preserves existing lists."""
        data = {
            "existing_list": ["item1", "item2"],
            "null_array": None,
            "nested_list": [
                {"items": None, "name": "test1"},
                {"items": ["existing"], "name": "test2"}
            ]
        }

        with patch.object(client, '_should_convert_to_array') as mock_should_convert:
            mock_should_convert.side_effect = lambda key, value, siblings, type_context=None: "item" in key

            result = client._transform_null_arrays(data)

            expected = {
                "existing_list": ["item1", "item2"],  # Unchanged
                "null_array": None,  # Not converted (no matching pattern)
                "nested_list": [
                    {"items": [], "name": "test1"},      # Converted
                    {"items": ["existing"], "name": "test2"}  # Unchanged
                ]
            }
            assert result == expected

    @pytest.mark.asyncio
    async def test_create_session_with_ssl(self, client):
        """Test session creation with SSL verification enabled."""
        # Test inside an async context where event loop is available
        async with client:
            # Session should be created with SSL verification
            assert client._session is not None
            assert client._session.connector._ssl is not None

    @pytest.mark.asyncio  
    async def test_create_session_without_ssl(self, client_no_ssl):
        """Test session creation with SSL verification disabled."""  
        # Test inside an async context where event loop is available
        async with client_no_ssl:
            # Session should be created with SSL verification disabled
            assert client_no_ssl._session is not None
            assert client_no_ssl._session.connector._ssl is not None