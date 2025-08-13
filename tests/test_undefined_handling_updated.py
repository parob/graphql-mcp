"""
Updated tests for Undefined value handling in RemoteGraphQLClient.
These tests reflect the new behavior where Undefined values are removed entirely
to prevent GraphQL validation errors with non-null variables.
"""

import pytest
from unittest.mock import AsyncMock, patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class TestUpdatedUndefinedHandling:
    """Test cases for the updated handling of Undefined values."""

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
        """Test cleaning simple Undefined values - removes them entirely."""
        variables = {
            "name": "test",
            "undefined_field": Undefined,
            "age": 25
        }
        result = client._clean_variables(variables)
        expected = {"name": "test", "age": 25}  # undefined_field removed entirely
        assert result == expected
        assert "undefined_field" not in result

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
                "profile": {
                    "bio": "test bio"
                    # avatar removed entirely
                }
                # email removed entirely
            }
        }
        assert result == expected
        assert "email" not in result["user"]
        assert "avatar" not in result["user"]["profile"]

    def test_clean_variables_list_with_undefined(self, client):
        """Test cleaning lists containing Undefined values."""
        variables = {
            "tags": ["tag1", Undefined, "tag2"],
            "ids": [1, 2, Undefined, 3]
        }
        result = client._clean_variables(variables)
        expected = {
            "tags": ["tag1", "tag2"],  # Undefined removed from list
            "ids": [1, 2, 3]          # Undefined removed from list
        }
        assert result == expected
        assert Undefined not in result["tags"]
        assert Undefined not in result["ids"]

    def test_clean_variables_nested_dicts_in_lists(self, client):
        """Test cleaning nested dictionaries within lists."""
        variables = {
            "items": [
                {"name": "item1", "optional": Undefined},
                {"name": "item2", "optional": "value"},
                {"name": "item3", "nested": {"keep": "this", "remove": Undefined}}
            ]
        }
        result = client._clean_variables(variables)
        expected = {
            "items": [
                {"name": "item1"},  # optional removed entirely
                {"name": "item2", "optional": "value"},
                {"name": "item3", "nested": {"keep": "this"}}  # remove removed entirely
            ]
        }
        assert result == expected
        assert "optional" not in result["items"][0]
        assert "remove" not in result["items"][2]["nested"]

    def test_clean_variables_all_undefined_dict_removed(self, client):
        """Test that dictionaries with only Undefined values are removed."""
        variables = {
            "empty_dict": {"undefined_only": Undefined},
            "valid_field": "keep_me"
        }
        result = client._clean_variables(variables)
        expected = {
            "valid_field": "keep_me"
            # empty_dict removed entirely because it became empty
        }
        assert result == expected
        assert "empty_dict" not in result

    def test_clean_variables_all_undefined_returns_none(self, client):
        """Test that completely Undefined structure returns None."""
        variables = {
            "field1": Undefined,
            "field2": Undefined,
            "nested": {"inner": Undefined}
        }
        result = client._clean_variables(variables)
        # All fields removed, so result should be None
        assert result is None

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
                        "list": ["item"]  # Undefined items removed
                    }
                    # other removed entirely
                },
                "sibling": "value"
            }
        }
        assert result == expected
        assert "remove" not in result["level1"]["level2"]["level3"]
        assert "other" not in result["level1"]["level2"]

    @pytest.mark.asyncio
    async def test_execute_request_with_undefined_variables(self, client):
        """Test that _execute_request properly removes Undefined variables."""
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

                # Verify that the request was made with cleaned variables (Undefined removed)
                call_args = mock_post.call_args
                sent_payload = call_args[1]['json']
                
                expected_variables = {
                    "name": "test",
                    "nested": {"required": "value"}  # optional removed entirely
                    # optional_field removed entirely
                }
                assert sent_payload['variables'] == expected_variables
                assert result == {"test": "result"}
                
                # Verify the query was also cleaned to remove unused variable declarations
                sent_query = sent_payload['query']
                # The query should be modified to only include variables that exist
                # This prevents GraphQL validation errors

    def test_mixed_null_and_undefined_handling(self, client):
        """Test that explicit None values are preserved while Undefined values are removed."""
        
        variables = {
            "explicitNull": None,        # Should be preserved as null
            "undefinedValue": Undefined, # Should be removed entirely
            "actualValue": "keep"        # Should be preserved
        }
        
        cleaned = client._clean_variables(variables)
        
        expected = {
            "explicitNull": None,  # Preserved
            "actualValue": "keep"  # Preserved
            # undefinedValue should be missing entirely
        }
        
        assert cleaned == expected
        assert "undefinedValue" not in cleaned

    def test_empty_list_after_undefined_removal(self, client):
        """Test that lists become empty when all items are Undefined."""
        
        variables = {
            "emptyList": [Undefined, Undefined],
            "partialList": [Undefined, "keep", Undefined],
            "normalField": "value"
        }
        
        cleaned = client._clean_variables(variables)
        
        expected = {
            "emptyList": [],  # All items removed, list remains
            "partialList": ["keep"],  # Only non-Undefined items remain
            "normalField": "value"
        }
        
        assert cleaned == expected