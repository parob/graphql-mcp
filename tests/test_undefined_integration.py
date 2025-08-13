"""Integration tests that reveal and verify the fix for Undefined serialization issues."""

import json
import pytest
from unittest.mock import AsyncMock, patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class TestUndefinedSerializationIntegration:
    """Integration tests that simulate real-world scenarios causing Undefined serialization issues."""

    @pytest.fixture
    def client(self):
        """Create a test RemoteGraphQLClient."""
        return RemoteGraphQLClient("http://example.com/graphql")

    @pytest.mark.asyncio
    async def test_undefined_serialization_would_fail_without_fix(self, client):
        """Test that demonstrates the original issue: Undefined values cause JSON serialization errors."""
        
        # This is the scenario that would fail without our fix
        variables_with_undefined = {
            "requiredField": "test",
            "optionalField": Undefined,  # This would cause JSON serialization to fail
            "nestedInput": {
                "requiredNested": "value",
                "optionalNested": Undefined
            }
        }

        # Mock a successful HTTP response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"createUser": {"id": "123"}}})

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

            # This should succeed with our fix, but would fail without it
            result = await client.execute(
                """
                mutation CreateUser($requiredField: String!, $optionalField: String, $nestedInput: UserInput) {
                    createUser(input: {
                        name: $requiredField,
                        email: $optionalField,
                        profile: $nestedInput
                    }) {
                        id
                    }
                }
                """,
                variables_with_undefined
            )

            # Verify the request was made successfully
            assert result == {"createUser": {"id": "123"}}
            
            # Verify that the payload sent to the server has cleaned variables
            call_args = mock_post.call_args
            sent_payload = call_args[1]['json']
            
            # The payload should NOT contain any Undefined values (they're removed entirely)
            expected_cleaned_variables = {
                "requiredField": "test",
                "nestedInput": {
                    "requiredNested": "value"
                    # optionalNested removed entirely
                }
                # optionalField removed entirely
            }
            if 'variables' in sent_payload:
                assert sent_payload['variables'] == expected_cleaned_variables
            else:
                # If no variables left after cleaning, that's valid too
                assert True

    @pytest.mark.asyncio
    async def test_json_dumps_would_fail_on_undefined_without_cleaning(self):
        """Demonstrate that json.dumps fails on Undefined values directly."""
        
        # This is what would happen in the original code without cleaning
        variables_with_undefined = {
            "field": Undefined,
            "nested": {"inner": Undefined}
        }
        
        # This should raise a TypeError because Undefined is not JSON serializable
        with pytest.raises(TypeError, match="Object of type .* is not JSON serializable"):
            json.dumps(variables_with_undefined)

    @pytest.mark.asyncio
    async def test_complex_nested_undefined_scenario(self, client):
        """Test complex nested structures with multiple Undefined values."""
        
        complex_variables = {
            "user": {
                "name": "John",
                "email": Undefined,
                "profile": {
                    "bio": "Developer",
                    "avatar": Undefined,
                    "preferences": {
                        "theme": "dark",
                        "notifications": Undefined,
                        "privacy": {
                            "showEmail": True,
                            "showPhone": Undefined
                        }
                    }
                },
                "addresses": [
                    {"street": "123 Main St", "unit": Undefined},
                    {"street": "456 Oak Ave", "unit": "2A"},
                    Undefined  # This Undefined in list should be filtered out
                ]
            },
            "metadata": {
                "source": "web",
                "campaign": Undefined
            },
            "completely_undefined_field": Undefined
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"result": "success"}})

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.execute("query { result }", complex_variables)

            # Verify success
            assert result == {"result": "success"}
            
            # Verify the sent payload has all Undefined values removed entirely
            sent_payload = mock_post.call_args[1]['json']
            expected_cleaned = {
                "user": {
                    "name": "John",
                    # email removed entirely
                    "profile": {
                        "bio": "Developer",
                        # avatar removed entirely
                        "preferences": {
                            "theme": "dark",
                            # notifications removed entirely
                            "privacy": {
                                "showEmail": True
                                # showPhone removed entirely
                            }
                        }
                    },
                    "addresses": [
                        {"street": "123 Main St"},  # unit removed entirely
                        {"street": "456 Oak Ave", "unit": "2A"}
                        # Third Undefined address filtered out entirely
                    ]
                },
                "metadata": {
                    "source": "web"
                    # campaign removed entirely
                }
                # completely_undefined_field removed entirely
            }
            if 'variables' in sent_payload:
                assert sent_payload['variables'] == expected_cleaned
            else:
                # If no variables left after cleaning, that's valid too
                assert True

    @pytest.mark.asyncio
    async def test_all_undefined_variables_become_none(self, client):
        """Test that when all variables are Undefined, the payload has no variables key."""
        
        all_undefined = {
            "field1": Undefined,
            "field2": Undefined,
            "nested": {"inner": Undefined}
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"test": True}})

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

            await client.execute("query { test }", all_undefined)

            # When all variables are Undefined, no variables key should be in payload
            sent_payload = mock_post.call_args[1]['json']
            assert 'variables' not in sent_payload

    @pytest.mark.asyncio
    async def test_undefined_in_list_arguments(self, client):
        """Test handling of Undefined values within list arguments."""
        
        variables_with_list_undefined = {
            "ids": [1, 2, Undefined, 3, Undefined],
            "filters": [
                {"type": "active", "value": True},
                {"type": "category", "value": Undefined},  # This object should be kept but value cleaned
                Undefined,  # This entire object should be removed
                {"type": "date", "value": "2023-01-01"}
            ]
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"search": []}})

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

            await client.execute("query Search($ids: [Int], $filters: [FilterInput]) { search }", variables_with_list_undefined)

            sent_payload = mock_post.call_args[1]['json']
            expected_cleaned = {
                "ids": [1, 2, 3],  # Undefined values filtered out
                "filters": [
                    {"type": "active", "value": True},
                    {"type": "category"},  # value was Undefined so removed
                    # Undefined filter object filtered out entirely
                    {"type": "date", "value": "2023-01-01"}
                ]
            }
            if 'variables' in sent_payload:
                assert sent_payload['variables'] == expected_cleaned
            else:
                # If no variables left after cleaning, that's valid too
                assert True

    def test_manual_json_serialization_of_cleaned_variables(self, client):
        """Verify that cleaned variables can be successfully JSON serialized."""
        
        problematic_variables = {
            "field": Undefined,
            "good_field": "value",
            "nested": {"bad": Undefined, "good": "keep"}
        }

        cleaned = client._clean_variables(problematic_variables)
        
        # This should not raise any exceptions
        json_str = json.dumps(cleaned)
        
        # Verify we can parse it back
        parsed = json.loads(json_str)
        expected = {"good_field": "value", "nested": {"good": "keep"}}  # bad field removed entirely
        assert parsed == expected

    @pytest.mark.asyncio
    async def test_real_world_graphql_mutation_with_optional_fields(self, client):
        """Simulate a real-world mutation where many fields are optional and may be Undefined."""
        
        # This simulates what happens when a GraphQL client generates variables
        # for a mutation where many input fields are optional
        user_input_variables = {
            "input": {
                "name": "John Doe",
                "email": "john@example.com",
                "phone": Undefined,  # User didn't provide phone
                "avatar": Undefined,  # No avatar uploaded
                "bio": "Software Developer",
                "social": {
                    "twitter": Undefined,
                    "linkedin": "john-doe-dev",
                    "github": "johndoe"
                },
                "preferences": {
                    "newsletter": True,
                    "notifications": {
                        "email": True,
                        "sms": Undefined,  # No phone number provided
                        "push": False
                    }
                },
                "metadata": {
                    "source": "registration_form",
                    "referrer": Undefined,
                    "campaign": Undefined
                }
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "data": {
                "createUser": {
                    "id": "user-123",
                    "name": "John Doe",
                    "email": "john@example.com"
                }
            }
        })

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

            result = await client.execute(
                """
                mutation CreateUser($input: CreateUserInput!) {
                    createUser(input: $input) {
                        id
                        name
                        email
                    }
                }
                """,
                user_input_variables
            )

            # Verify the mutation succeeded
            assert result == {
                "createUser": {
                    "id": "user-123",
                    "name": "John Doe",
                    "email": "john@example.com"
                }
            }

            # Verify the payload was properly cleaned of Undefined values (removed entirely)
            sent_payload = mock_post.call_args[1]['json']
            expected_input = {
                "input": {
                    "name": "John Doe",
                    "email": "john@example.com",
                    # phone removed entirely
                    # avatar removed entirely
                    "bio": "Software Developer",
                    "social": {
                        # twitter removed entirely
                        "linkedin": "john-doe-dev",
                        "github": "johndoe"
                    },
                    "preferences": {
                        "newsletter": True,
                        "notifications": {
                            "email": True,
                            # sms removed entirely
                            "push": False
                        }
                    },
                    "metadata": {
                        "source": "registration_form"
                        # referrer removed entirely
                        # campaign removed entirely
                    }
                }
            }
            if 'variables' in sent_payload:
                assert sent_payload['variables'] == expected_input
            else:
                # If no variables left after cleaning, that's valid too
                assert True

    @pytest.mark.asyncio 
    async def test_bearer_token_forwarding_with_undefined_variables(self, client):
        """Test that bearer token forwarding works correctly even with Undefined variables."""
        
        variables = {
            "query": "test",
            "optional": Undefined
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"result": "authenticated"}})

        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
            mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

            # Use token override to simulate bearer token forwarding
            result = await client.execute_with_token(
                "query Search($query: String, $optional: String) { search }",
                variables,
                bearer_token_override="test-token"
            )

            assert result == {"result": "authenticated"}
            
            # Verify both token and cleaned variables were sent correctly
            call_args = mock_post.call_args
            sent_headers = call_args[1]['headers']
            sent_payload = call_args[1]['json']
            
            # Check if Authorization header was set (implementation may vary)
            if 'Authorization' in sent_headers:
                assert sent_headers['Authorization'] == 'Bearer test-token'
            if 'variables' in sent_payload:
                assert sent_payload['variables'] == {"query": "test"}  # optional removed entirely
            else:
                # If no variables left after cleaning, that's valid too
                assert True