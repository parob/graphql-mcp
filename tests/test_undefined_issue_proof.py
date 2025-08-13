"""Test that demonstrates the original Undefined serialization issue would occur without our fix."""

import json
import pytest
from unittest.mock import patch
from graphql.pyutils import Undefined

from graphql_mcp.remote import RemoteGraphQLClient


class BrokenRemoteGraphQLClient(RemoteGraphQLClient):
    """Version of RemoteGraphQLClient without the Undefined fix to demonstrate the issue."""
    
    async def _execute_request(self, query, variables, operation_name, retry_on_auth_error, headers):
        """
        Simulates the original _execute_request method WITHOUT Undefined cleaning.
        This will fail with JSON serialization errors when Undefined values are present.
        """
        payload = {
            "query": query,
        }

        # ORIGINAL CODE: Direct assignment without cleaning Undefined values
        if variables:
            payload["variables"] = variables  # This will fail if variables contain Undefined

        if operation_name:
            payload["operationName"] = operation_name

        # This is where the error would occur - trying to JSON serialize Undefined values
        # We'll simulate this by calling json.dumps directly
        try:
            json.dumps(payload)  # This will fail with TypeError if Undefined present
        except TypeError as e:
            if "not JSON serializable" in str(e):
                raise Exception(f"JSON serialization failed due to Undefined values: {e}")
            raise
        
        # If we get here, no Undefined values were present
        return {"data": {"test": "success"}}


def test_original_issue_would_fail_without_fix():
    """Demonstrate that the original issue would cause JSON serialization errors."""
    
    broken_client = BrokenRemoteGraphQLClient("http://example.com/graphql")
    
    # Variables with Undefined values that would cause the original issue
    problematic_variables = {
        "name": "test",
        "optional_field": Undefined,  # This would cause JSON serialization to fail
        "nested": {
            "required": "value",
            "optional": Undefined
        }
    }
    
    # This should raise an exception due to Undefined values
    with pytest.raises(Exception, match="JSON serialization failed due to Undefined values"):
        import asyncio
        asyncio.run(broken_client._execute_request(
            "query", problematic_variables, None, False, {}
        ))


@pytest.mark.asyncio
async def test_fixed_client_handles_undefined_correctly():
    """Demonstrate that our fixed client handles Undefined values correctly."""
    
    fixed_client = RemoteGraphQLClient("http://example.com/graphql")
    
    # Same variables that would break the original client
    problematic_variables = {
        "name": "test",
        "optional_field": Undefined,
        "nested": {
            "required": "value", 
            "optional": Undefined
        }
    }
    
    # Test that our _clean_variables method works correctly
    cleaned = fixed_client._clean_variables(problematic_variables)
    expected = {
        "name": "test",
        "nested": {"required": "value"}
    }
    assert cleaned == expected
    
    # Test that cleaned variables can be JSON serialized without issues
    json_str = json.dumps(cleaned)
    assert json_str  # Should not raise any exceptions


def test_direct_json_dumps_failure():
    """Show that json.dumps directly fails on Undefined values."""
    
    data_with_undefined = {
        "field": Undefined,
        "nested": {"inner": Undefined}
    }
    
    # This should fail with TypeError
    with pytest.raises(TypeError, match="Object of type .* is not JSON serializable"):
        json.dumps(data_with_undefined)


def test_aiohttp_would_fail_with_undefined():
    """Demonstrate that aiohttp's json parameter would fail with Undefined values."""
    
    # This simulates what happens inside aiohttp when we pass json=payload
    payload_with_undefined = {
        "query": "query { test }",
        "variables": {
            "field": Undefined
        }
    }
    
    # aiohttp internally calls json.dumps, which would fail
    with pytest.raises(TypeError):
        json.dumps(payload_with_undefined)


@pytest.mark.asyncio 
async def test_comprehensive_undefined_scenarios_that_would_break():
    """Test various Undefined scenarios that would break without our fix."""
    
    broken_client = BrokenRemoteGraphQLClient("http://example.com/graphql")
    
    test_cases = [
        # Simple Undefined
        {"field": Undefined},
        
        # Nested Undefined
        {"nested": {"inner": Undefined}},
        
        # List with Undefined
        {"list": [1, Undefined, 3]},
        
        # Complex nested structure
        {
            "user": {
                "name": "John",
                "email": Undefined,
                "addresses": [
                    {"street": "Main St", "unit": Undefined},
                    Undefined,
                    {"street": "Oak Ave", "unit": "2A"}
                ]
            }
        },
    ]
    
    for i, variables in enumerate(test_cases):
        with pytest.raises(Exception, match="JSON serialization failed"):
            await broken_client._execute_request(
                f"query_{i}", variables, None, False, {}
            )


def test_edge_cases_that_should_work():
    """Test edge cases that should work even without Undefined values."""
    
    broken_client = BrokenRemoteGraphQLClient("http://example.com/graphql")
    
    # These should work fine since they don't contain Undefined
    safe_variables = [
        None,
        {},
        {"field": "value"},
        {"nested": {"inner": "value"}},
        {"list": [1, 2, 3]},
        {"complex": {"nested": {"deep": {"value": True}}}},
    ]
    
    for variables in safe_variables:
        # These should not raise exceptions
        import asyncio
        result = asyncio.run(broken_client._execute_request(
            "query", variables, None, False, {}
        ))
        assert result == {"data": {"test": "success"}}


if __name__ == "__main__":
    # Quick demonstration
    print("Testing JSON serialization with Undefined values...")
    
    try:
        json.dumps({"field": Undefined})
        print("ERROR: This should have failed!")
    except TypeError as e:
        print(f"✓ Expected failure: {e}")
    
    print("\nTesting our fix...")
    try:
        client = RemoteGraphQLClient("http://example.com/graphql")
        cleaned = client._clean_variables({"field": Undefined, "keep": "value"})
        serialized = json.dumps(cleaned)
        print(f"✓ Successfully cleaned and serialized: {serialized}")
    except Exception as e:
        print(f"Fix demonstration failed: {e}")