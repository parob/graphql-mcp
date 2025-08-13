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
        expected = {"name": "test", "age": 25}
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
                "profile": {
                    "bio": "test bio"
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
            "tags": ["tag1", "tag2"],
            "ids": [1, 2, 3]
        }
        assert result == expected

    def test_clean_variables_nested_dicts_in_lists(self, client):
        """Test cleaning nested dictionaries within lists."""
        variables = {
            "items": [
                {"name": "item1", "optional": Undefined},
                {"name": "item2", "optional": "value"},
                Undefined,  # This entire item should be filtered out
                {"name": "item3", "nested": {"keep": "this", "remove": Undefined}}
            ]
        }
        result = client._clean_variables(variables)
        expected = {
            "items": [
                {"name": "item1"},
                {"name": "item2", "optional": "value"},
                {"name": "item3", "nested": {"keep": "this"}}
            ]
        }
        assert result == expected

    def test_clean_variables_empty_after_cleaning(self, client):
        """Test that empty structures after cleaning are removed."""
        variables = {
            "empty_dict": {"undefined_only": Undefined},
            "empty_list": [Undefined, Undefined],
            "valid_field": "keep_me"
        }
        result = client._clean_variables(variables)
        expected = {"valid_field": "keep_me"}
        assert result == expected

    def test_clean_variables_all_undefined(self, client):
        """Test that completely Undefined structure returns None."""
        variables = {
            "field1": Undefined,
            "field2": Undefined,
            "nested": {"inner": Undefined}
        }
        result = client._clean_variables(variables)
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
                        "list": ["item"]
                    }
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
                "nested": {"required": "value"}
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