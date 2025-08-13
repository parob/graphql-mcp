"""
Comprehensive tests for the automatic GraphQL schema deduction system.

This test suite ensures that the system correctly:
1. Automatically discovers field types from GraphQL introspection
2. Converts null values to arrays based on schema information only
3. Handles nested type contexts without manual mappings
4. Works with complex GraphQL schemas without hardcoded inference
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class TestAutomaticSchemaDeduction:
    """Test automatic GraphQL schema deduction and type-aware transformations."""

    @pytest.fixture
    def client(self):
        return RemoteGraphQLClient("http://example.com/graphql")

    @pytest.fixture
    def mock_complete_schema(self):
        """Complete GraphQL schema for comprehensive testing."""
        return {
            "__schema": {
                "types": [
                    {
                        "name": "Query",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "users", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "User"}}},
                            {"name": "user", "type": {"kind": "OBJECT", "name": "User"}},
                            {"name": "products", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Product"}}},
                            {"name": "orders", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Order"}}},
                            {"name": "totalCount", "type": {"kind": "SCALAR", "name": "Int"}}
                        ]
                    },
                    {
                        "name": "Mutation",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "createUser", "type": {"kind": "OBJECT", "name": "User"}},
                            {"name": "updateProduct", "type": {"kind": "OBJECT", "name": "Product"}},
                            {"name": "deleteOrder", "type": {"kind": "SCALAR", "name": "Boolean"}}
                        ]
                    },
                    {
                        "name": "User",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "id", "type": {"kind": "NON_NULL", "ofType": {"kind": "SCALAR", "name": "ID"}}},
                            {"name": "name", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "email", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "tags", "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}}},
                            {"name": "addresses", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Address"}}},
                            {"name": "orders", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Order"}}},
                            {"name": "profile", "type": {"kind": "OBJECT", "name": "Profile"}},
                            {"name": "settings", "type": {"kind": "OBJECT", "name": "UserSettings"}}
                        ]
                    },
                    {
                        "name": "Profile",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "bio", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "avatar", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "socialLinks", "type": {"kind": "LIST", "ofType": {"kind": "SCALAR", "name": "String"}}},
                            {"name": "skills", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Skill"}}}
                        ]
                    },
                    {
                        "name": "UserSettings",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "theme", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "notifications", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "NotificationPref"}}},
                            {"name": "privacy", "type": {"kind": "OBJECT", "name": "PrivacySettings"}}
                        ]
                    },
                    {
                        "name": "Product",
                        "kind": "OBJECT", 
                        "fields": [
                            {"name": "id", "type": {"kind": "SCALAR", "name": "ID"}},
                            {"name": "name", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "categories", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Category"}}},
                            {"name": "reviews", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Review"}}},
                            {"name": "variants", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "ProductVariant"}}}
                        ]
                    },
                    {
                        "name": "Order",
                        "kind": "OBJECT",
                        "fields": [
                            {"name": "id", "type": {"kind": "SCALAR", "name": "ID"}},
                            {"name": "status", "type": {"kind": "SCALAR", "name": "String"}},
                            {"name": "items", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "OrderItem"}}},
                            {"name": "payments", "type": {"kind": "LIST", "ofType": {"kind": "OBJECT", "name": "Payment"}}}
                        ]
                    }
                ]
            }
        }

    def test_schema_introspection_caching(self, client, mock_complete_schema):
        """Test that schema introspection correctly caches field type information."""
        
        with patch.object(client, '_raw_execute_request', return_value=mock_complete_schema):
            # Trigger schema introspection
            asyncio.run(client._introspect_schema())
            
            # Verify introspection completed
            assert client._introspected is True
            
            # Verify array fields are correctly identified
            assert client._array_fields_cache["User"]["tags"] is True
            assert client._array_fields_cache["User"]["addresses"] is True
            assert client._array_fields_cache["User"]["orders"] is True
            assert client._array_fields_cache["User"]["name"] is False
            assert client._array_fields_cache["User"]["email"] is False
            
            # Verify field-to-type mappings are created
            assert "Query.users" in client._field_type_map
            assert client._field_type_map["Query.users"] == "User"
            assert "User.profile" in client._field_type_map
            assert client._field_type_map["User.profile"] == "Profile"
            
            # Verify fallback mappings work
            assert client._field_type_map["profile"] == "Profile"
            assert client._field_type_map["createUser"] == "User"

    def test_automatic_null_to_array_conversion(self, client, mock_complete_schema):
        """Test automatic null-to-array conversion based on schema."""
        
        with patch.object(client, '_raw_execute_request', return_value=mock_complete_schema):
            asyncio.run(client._introspect_schema())
            
            # Test data with null values that should be converted based on schema
            test_data = {
                "users": None,      # Query.users is LIST -> should become []
                "totalCount": None, # Query.totalCount is SCALAR -> should stay None
                "user": {           # Query.user returns User object
                    "name": None,       # User.name is SCALAR -> should stay None
                    "tags": None,       # User.tags is LIST -> should become []
                    "addresses": None,  # User.addresses is LIST -> should become []
                    "profile": {        # User.profile returns Profile object
                        "bio": None,            # Profile.bio is SCALAR -> should stay None
                        "socialLinks": None,    # Profile.socialLinks is LIST -> should become []
                        "skills": None          # Profile.skills is LIST -> should become []
                    },
                    "settings": {       # User.settings returns UserSettings object
                        "theme": None,          # UserSettings.theme is SCALAR -> should stay None
                        "notifications": None   # UserSettings.notifications is LIST -> should become []
                    }
                }
            }
            
            result = client._transform_null_arrays(test_data, type_context="Query")
            
            expected = {
                "users": [],        # Automatically converted (LIST)
                "totalCount": None, # Not converted (SCALAR)
                "user": {
                    "name": None,           # Not converted (SCALAR)
                    "tags": [],             # Automatically converted (LIST)
                    "addresses": [],        # Automatically converted (LIST)
                    "profile": {
                        "bio": None,            # Not converted (SCALAR)
                        "socialLinks": [],      # Automatically converted (LIST)
                        "skills": []            # Automatically converted (LIST)
                    },
                    "settings": {
                        "theme": None,          # Not converted (SCALAR)
                        "notifications": []     # Automatically converted (LIST)
                    }
                }
            }
            
            assert result == expected

    def test_mutation_response_transformation(self, client, mock_complete_schema):
        """Test automatic transformation of mutation responses."""
        
        with patch.object(client, '_raw_execute_request', return_value=mock_complete_schema):
            asyncio.run(client._introspect_schema())
            
            # Mock a createUser mutation response
            mutation_response = {
                "createUser": {
                    "id": "123",
                    "name": "John Doe",
                    "tags": None,       # Should become []
                    "addresses": None,  # Should become []
                    "orders": None,     # Should become []
                    "profile": {
                        "bio": "Developer",
                        "socialLinks": None,  # Should become []
                        "skills": None        # Should become []
                    }
                }
            }
            
            result = client._transform_null_arrays(mutation_response, type_context="Mutation")
            
            expected = {
                "createUser": {
                    "id": "123",
                    "name": "John Doe", 
                    "tags": [],         # Automatically converted
                    "addresses": [],    # Automatically converted
                    "orders": [],       # Automatically converted
                    "profile": {
                        "bio": "Developer",
                        "socialLinks": [],  # Automatically converted
                        "skills": []        # Automatically converted
                    }
                }
            }
            
            assert result == expected

    def test_complex_nested_structures(self, client, mock_complete_schema):
        """Test automatic handling of complex nested GraphQL structures."""
        
        with patch.object(client, '_raw_execute_request', return_value=mock_complete_schema):
            asyncio.run(client._introspect_schema())
            
            # Complex nested data structure
            complex_data = {
                "products": [
                    {
                        "id": "prod1",
                        "name": "Laptop",
                        "categories": None,     # Product.categories is LIST -> []
                        "reviews": None,        # Product.reviews is LIST -> []
                        "variants": None        # Product.variants is LIST -> []
                    },
                    {
                        "id": "prod2", 
                        "name": "Phone",
                        "categories": [{"name": "Electronics"}],
                        "reviews": None,        # Should become []
                        "variants": None        # Should become []
                    }
                ],
                "orders": [
                    {
                        "id": "order1",
                        "status": "pending",
                        "items": None,          # Order.items is LIST -> []
                        "payments": None        # Order.payments is LIST -> []
                    }
                ]
            }
            
            result = client._transform_null_arrays(complex_data, type_context="Query")
            
            expected = {
                "products": [
                    {
                        "id": "prod1",
                        "name": "Laptop",
                        "categories": [],       # Automatically converted
                        "reviews": [],          # Automatically converted
                        "variants": []          # Automatically converted
                    },
                    {
                        "id": "prod2",
                        "name": "Phone", 
                        "categories": [{"name": "Electronics"}],
                        "reviews": [],          # Automatically converted
                        "variants": []          # Automatically converted
                    }
                ],
                "orders": [
                    {
                        "id": "order1",
                        "status": "pending",
                        "items": [],            # Automatically converted
                        "payments": []          # Automatically converted
                    }
                ]
            }
            
            assert result == expected

    def test_no_schema_fallback_behavior(self, client):
        """Test behavior when no schema is available (should not convert based on field names)."""
        
        # Don't call _introspect_schema, so _introspected remains False
        test_data = {
            "users": None,      # Would have been converted with old heuristics
            "items": None,      # Would have been converted with old heuristics
            "results": None,    # Would have been converted with old heuristics
            "name": None        # Should stay None (never had heuristics)
        }
        
        result = client._transform_null_arrays(test_data)
        
        # Without schema, no automatic conversion should happen
        expected = {
            "users": None,      # No conversion without schema
            "items": None,      # No conversion without schema
            "results": None,    # No conversion without schema
            "name": None
        }
        
        assert result == expected

    def test_sibling_analysis_still_works(self, client):
        """Test that sibling analysis still works when schema is unavailable."""
        
        # No schema introspection
        test_data = {
            "products": [
                {"categories": None, "name": "Product 1"},
                {"categories": ["Electronics"], "name": "Product 2"},  # Sibling evidence
                {"categories": None, "name": "Product 3"}
            ]
        }
        
        result = client._transform_null_arrays(test_data)
        
        # Sibling analysis should convert categories to []
        expected = {
            "products": [
                {"categories": [], "name": "Product 1"},        # Converted due to sibling
                {"categories": ["Electronics"], "name": "Product 2"},
                {"categories": [], "name": "Product 3"}         # Converted due to sibling
            ]
        }
        
        assert result == expected

    @pytest.mark.asyncio
    async def test_end_to_end_automatic_workflow(self, client, mock_complete_schema):
        """Test the complete end-to-end workflow with automatic schema deduction."""
        
        # Variables with Undefined values
        variables = {
            "name": "John Doe",
            "email": Undefined,  # Will be removed
            "tags": ["dev", Undefined, "python"]  # Undefined filtered out
        }
        
        # Mock response with nulls that should be transformed
        mock_response_data = {
            "data": {
                "createUser": {
                    "id": "123",
                    "name": "John Doe",
                    "tags": None,       # Should become []
                    "addresses": None,  # Should become []
                    "profile": {
                        "bio": None,        # Should stay None (scalar)
                        "socialLinks": None # Should become []
                    }
                }
            }
        }
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_response_data)
        
        with patch.object(client, '_raw_execute_request', return_value=mock_complete_schema):
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
                
                # Execute the request - should automatically introspect and transform
                result = await client.execute(
                    "mutation CreateUser($name: String!, $email: String) { createUser { id name } }",
                    variables
                )
                
                # Verify Undefined values were cleaned
                call_args = mock_post.call_args
                sent_payload = call_args[1]['json']
                assert "email" not in sent_payload['variables']  # Removed
                assert sent_payload['variables']['tags'] == ["dev", "python"]  # Filtered
                
                # Verify automatic null-to-array transformation happened
                expected_result = {
                    "createUser": {
                        "id": "123",
                        "name": "John Doe",
                        "tags": [],         # Automatically converted (LIST)
                        "addresses": [],    # Automatically converted (LIST)
                        "profile": {
                            "bio": None,        # Not converted (SCALAR)
                            "socialLinks": []   # Automatically converted (LIST)
                        }
                    }
                }
                
                assert result == expected_result

    def test_field_type_extraction(self, client):
        """Test the _extract_type_name method handles all GraphQL type variations."""
        
        # Test simple named type
        simple_type = {"name": "User", "kind": "OBJECT"}
        assert client._extract_type_name(simple_type) == "User"
        
        # Test NON_NULL wrapper
        non_null_type = {
            "kind": "NON_NULL",
            "ofType": {"name": "String", "kind": "SCALAR"}
        }
        assert client._extract_type_name(non_null_type) == "String"
        
        # Test LIST wrapper
        list_type = {
            "kind": "LIST", 
            "ofType": {"name": "User", "kind": "OBJECT"}
        }
        assert client._extract_type_name(list_type) == "User"
        
        # Test nested wrappers (NON_NULL wrapping LIST)
        nested_type = {
            "kind": "NON_NULL",
            "ofType": {
                "kind": "LIST",
                "ofType": {"name": "String", "kind": "SCALAR"}
            }
        }
        assert client._extract_type_name(nested_type) == "String"

    def test_performance_with_large_schema(self, client):
        """Test that large schemas are handled efficiently."""
        
        # Create a large schema with 100 types, each with 20 fields
        large_schema = {
            "__schema": {
                "types": [
                    {
                        "name": f"Type{i}",
                        "kind": "OBJECT",
                        "fields": [
                            {
                                "name": f"field{j}",
                                "type": {"kind": "LIST" if j % 3 == 0 else "SCALAR", 
                                        "ofType": {"name": "String", "kind": "SCALAR"} if j % 3 == 0 else None,
                                        "name": "String" if j % 3 != 0 else None}
                            }
                            for j in range(20)
                        ]
                    }
                    for i in range(100)
                ]
            }
        }
        
        with patch.object(client, '_raw_execute_request', return_value=large_schema):
            # Should complete quickly even with large schema
            import time
            start_time = time.time()
            asyncio.run(client._introspect_schema())
            end_time = time.time()
            
            # Should complete in well under a second
            assert end_time - start_time < 1.0
            
            # Should have processed all types and fields
            assert len(client._array_fields_cache) == 100
            assert len(client._field_type_map) > 2000  # 100 types * 20 fields * 2 (qualified + simple names)