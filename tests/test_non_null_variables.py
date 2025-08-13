"""
Test handling of non-null GraphQL variables with Undefined values.
This addresses the specific issue where non-null variables (marked with !) 
cannot receive null values and must be completely omitted.
"""

import pytest
from unittest.mock import AsyncMock, patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class TestNonNullVariables:
    """Test handling of non-null GraphQL variables."""
    
    @pytest.fixture
    def client(self):
        """Create a test RemoteGraphQLClient."""
        return RemoteGraphQLClient("http://example.com/graphql")
    
    def test_remove_non_null_undefined_variables_from_query(self, client):
        """Test that undefined variables are removed from non-null variable declarations."""
        
        # This is the problematic scenario from the error logs
        query = """
        query GetMeasurements($dateGrouping: DateGrouping!, $valueGrouping: GroupingFunc!, $optionalParam: String) {
            measurements(dateGrouping: $dateGrouping, valueGrouping: $valueGrouping, param: $optionalParam) {
                value
            }
        }
        """
        
        # Only provide the optional parameter, not the required ones
        variables = {
            "optionalParam": "test",
            "dateGrouping": Undefined,    # This should be completely removed
            "valueGrouping": Undefined,   # This should be completely removed
        }
        
        # Clean variables should remove undefined ones entirely
        cleaned = client._clean_variables(variables)
        
        # Only optionalParam should remain
        expected_cleaned = {"optionalParam": "test"}
        assert cleaned == expected_cleaned
        
        # Query should be modified to remove unused variable declarations
        modified_query = client._remove_unused_variables_from_query(query, cleaned)
        
        # Should only have the optionalParam declaration
        expected_query = """
        query GetMeasurements($optionalParam: String) {
            measurements(dateGrouping: $dateGrouping, valueGrouping: $valueGrouping, param: $optionalParam) {
                value
            }
        }
        """
        
        # Check that non-null variable declarations were removed
        assert "$dateGrouping: DateGrouping!" not in modified_query
        assert "$valueGrouping: GroupingFunc!" not in modified_query
        assert "$optionalParam: String" in modified_query
    
    def test_clean_variables_removes_undefined_completely(self, client):
        """Test that _clean_variables removes Undefined values entirely, not converting to None."""
        
        variables = {
            "requiredField": "value",
            "undefinedField": Undefined,
            "nested": {
                "keep": "this",
                "remove": Undefined
            },
            "list": ["keep", Undefined, "this"]
        }
        
        cleaned = client._clean_variables(variables)
        
        # Undefined values should be removed entirely, not converted to None
        expected = {
            "requiredField": "value",
            # undefinedField should be completely missing
            "nested": {
                "keep": "this"
                # "remove" should be completely missing
            },
            "list": ["keep", "this"]  # Undefined items should be filtered out
        }
        
        assert cleaned == expected
        assert "undefinedField" not in cleaned
        assert "remove" not in cleaned["nested"]
        assert None not in cleaned["list"]
        assert Undefined not in cleaned["list"]
    
    def test_complex_non_null_scenario(self, client):
        """Test the exact scenario from the error logs."""
        
        # Simulate the actual query that was failing
        query = """
        query ($dateGrouping: DateGrouping!, $valueGrouping: GroupingFunc!, $startTime: DateTime, $endTime: DateTime) {
            aggregatedMeasurements(
                dateGrouping: $dateGrouping,
                valueGrouping: $valueGrouping,
                startTime: $startTime,
                endTime: $endTime
            ) {
                timestamp
                value
            }
        }
        """
        
        # This represents what happens when MCP tools don't provide required parameters
        variables = {
            "dateGrouping": Undefined,    # Required but not provided
            "valueGrouping": Undefined,   # Required but not provided  
            "startTime": "2025-01-01",
            "endTime": Undefined          # Optional, not provided
        }
        
        # Clean variables
        cleaned = client._clean_variables(variables)
        
        # Only startTime should remain
        expected_cleaned = {"startTime": "2025-01-01"}
        assert cleaned == expected_cleaned
        
        # Modify query to remove declarations for missing variables
        modified_query = client._remove_unused_variables_from_query(query, cleaned)
        
        # Should only have startTime declaration
        assert "$dateGrouping: DateGrouping!" not in modified_query
        assert "$valueGrouping: GroupingFunc!" not in modified_query
        assert "$endTime: DateTime" not in modified_query
        assert "$startTime: DateTime" in modified_query
        
        # The modified query should be valid GraphQL (though it might not be semantically correct)
        # This prevents the "must not be null" validation error
        assert "($startTime: DateTime)" in modified_query
    
    @pytest.mark.asyncio
    async def test_execute_with_non_null_undefined_variables(self, client):
        """Test that execute properly handles non-null undefined variables."""
        
        query = """
        query TestQuery($required: String!, $optional: String) {
            test(required: $required, optional: $optional) {
                result
            }
        }
        """
        
        variables = {
            "required": Undefined,  # This should cause the variable to be removed
            "optional": "test"
        }
        
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": {"test": {"result": "success"}}})
        
        with patch.object(client, '_introspect_schema', new_callable=AsyncMock):
            with patch('aiohttp.ClientSession.post') as mock_post:
                mock_post.return_value.__aenter__ = AsyncMock(return_value=mock_response)
                mock_post.return_value.__aexit__ = AsyncMock(return_value=None)
                
                result = await client.execute(query, variables)
                
                # Should succeed without GraphQL validation errors
                assert result == {"test": {"result": "success"}}
                
                # Check what was actually sent to the server
                call_args = mock_post.call_args
                sent_payload = call_args[1]['json']
                
                # Should only have optional variable
                assert sent_payload['variables'] == {"optional": "test"}
                
                # Query should be modified to remove required variable declaration
                sent_query = sent_payload['query']
                assert "$required: String!" not in sent_query
                assert "$optional: String" in sent_query
    
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