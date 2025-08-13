"""Integration test demonstrating all the fixes working together."""

import pytest
from unittest.mock import AsyncMock, patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class TestCompleteFixes:
    """Test all the fixes working together."""

    @pytest.fixture
    def client(self):
        return RemoteGraphQLClient("http://example.com/graphql")

    @pytest.mark.asyncio
    async def test_all_fixes_working_together(self, client):
        """Test that all improvements work together in a realistic scenario."""
        
        # Variables with Undefined values (would cause original issue)
        variables = {
            "name": "John Doe",
            "email": Undefined,  # Optional field not provided
            "profile": {
                "bio": "Developer", 
                "avatar": Undefined  # Optional nested field
            },
            "tags": ["dev", Undefined, "python"],  # List with Undefined
            "preferences": {
                "notifications": True,
                "theme": Undefined  # Optional preference
            }
        }

        # Mock response with null arrays (would need transformation)
        mock_response_data = {
            "data": {
                "createUser": {
                    "id": "123",
                    "name": "John Doe",
                    "tags": None,  # This should become []
                    "addresses": None,  # This should become []
                    "bio": None  # This should stay None
                }
            }
        }

        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)

        # Mock schema introspection to avoid interfering with the test
        with patch.object(client, '_introspect_schema', new_callable=AsyncMock):
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post.return_value.__aexit__ = AsyncMock(return_value=None)

                # Execute the request
                result = await client.execute(
                    """
                    mutation CreateUser($name: String!, $email: String, $profile: ProfileInput) {
                        createUser(name: $name, email: $email, profile: $profile) {
                            id
                            name
                        }
                    }
                    """,
                    variables
                )

            # Verify the fixes worked:
            
            # 1. Undefined values were converted to None (not removed)
            call_args = mock_post.call_args
            sent_payload = call_args[1]['json']
            expected_variables = {
                "name": "John Doe",
                "email": None,  # Undefined converted to None
                "profile": {
                    "bio": "Developer",
                    "avatar": None  # Undefined converted to None
                },
                "tags": ["dev", None, "python"],  # Undefined in list converted to None
                "preferences": {
                    "notifications": True,
                    "theme": None  # Undefined converted to None
                }
            }
            assert sent_payload['variables'] == expected_variables
            
            # 2. Response data null arrays were transformed to empty arrays
            expected_result = {
                "createUser": {
                    "id": "123", 
                    "name": "John Doe",
                    "tags": [],  # null became []
                    "addresses": [],  # null became []
                    "bio": None  # null stayed None (not array-like field)
                }
            }
            assert result == expected_result

    def test_undefined_to_none_conversion(self, client):
        """Test that Undefined values are converted to None (JSON serializable)."""
        
        variables = {
            "field1": Undefined,
            "field2": "keep",
            "nested": {
                "inner1": Undefined,
                "inner2": "also keep"
            },
            "list": [Undefined, "item", Undefined]
        }
        
        cleaned = client._clean_variables(variables)
        
        # Should convert Undefined to None, making it JSON serializable
        import json
        json_str = json.dumps(cleaned)  # This should not raise an exception
        
        expected = {
            "field1": None,
            "field2": "keep", 
            "nested": {
                "inner1": None,
                "inner2": "also keep"
            },
            "list": [None, "item", None]
        }
        assert cleaned == expected

    def test_query_variable_cleaning(self, client):
        """Test that unused variable declarations are removed from queries."""
        
        # Query with multiple variables but only some provided
        query = "query GetData($id: ID!, $name: String, $age: Int, $active: Boolean) { user }"
        variables = {"id": "123", "age": 25}  # name and active not provided
        
        cleaned_query = client._remove_unused_variables_from_query(query, variables)
        expected = "query GetData($id: ID!, $age: Int) { user }"
        
        assert cleaned_query == expected

    def test_null_array_transformation(self, client):
        """Test that null values are converted to empty arrays for array-like fields."""
        
        data = {
            "user": {
                "name": "John",
                "emails": None,  # Should become []
                "bio": None,     # Should stay None
                "tags": None,    # Should become []
                "preferences": {
                    "items": None,      # Should become []
                    "setting": None     # Should stay None
                }
            },
            "results": None,  # Should become []
            "count": None     # Should stay None
        }
        
        transformed = client._transform_null_arrays(data)
        expected = {
            "user": {
                "name": "John", 
                "emails": [],    # null became []
                "bio": None,     # stayed None
                "tags": [],      # null became []
                "preferences": {
                    "items": [],     # null became []
                    "setting": None  # stayed None
                }
            },
            "results": [],   # null became []
            "count": None    # stayed None
        }
        
        assert transformed == expected

    def test_comprehensive_real_world_scenario(self, client):
        """Test a comprehensive scenario combining all fixes."""
        
        # This represents what would happen in a real GraphQL client
        # with optional fields, some undefined, and response transformation
        
        # 1. Clean variables (Undefined -> None)
        raw_variables = {
            "input": {
                "name": "Test User",
                "email": Undefined,
                "preferences": {
                    "theme": "dark",
                    "notifications": Undefined
                },
                "tags": ["user", Undefined, "test"]
            }
        }
        
        cleaned_vars = client._clean_variables(raw_variables)
        
        # 2. Clean query (remove unused variable declarations)  
        query = "mutation Create($input: UserInput!, $unused: String) { createUser }"
        clean_query = client._remove_unused_variables_from_query(query, cleaned_vars)
        
        # 3. Transform response (null arrays -> [])
        mock_response = {
            "users": None,
            "profile": {
                "tags": None,
                "bio": "Test bio"
            }
        }
        
        transformed_response = client._transform_null_arrays(mock_response)
        
        # Verify all transformations
        assert cleaned_vars == {
            "input": {
                "name": "Test User",
                "email": None,  # Undefined -> None
                "preferences": {
                    "theme": "dark",
                    "notifications": None  # Undefined -> None
                },
                "tags": ["user", None, "test"]  # Undefined -> None
            }
        }
        
        assert clean_query == "mutation Create($input: UserInput!) { createUser }"
        
        assert transformed_response == {
            "users": [],  # null -> []
            "profile": {
                "tags": [],  # null -> []
                "bio": "Test bio"
            }
        }
        
        # Verify final result is JSON serializable
        import json
        json.dumps(cleaned_vars)  # Should not raise
        json.dumps(transformed_response)  # Should not raise