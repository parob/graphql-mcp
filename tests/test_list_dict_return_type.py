"""
Test for List[Dict] return type handling.

When a GraphQL field returns List[Dict], the MCP tool should return
the data as a properly structured list of dictionaries, not as
JSON-stringified TextContent.
"""

import pytest
import sys
import json

sys.path.insert(0, 'tests')


@pytest.mark.asyncio
async def test_list_dict_return_type():
    """
    Test that List[Dict] return types are properly handled.

    The issue: When calling a tool that returns List[Dict], the result
    comes back as TextContent with JSON-stringified dictionaries instead
    of actual dictionary structures.

    Expected: The result should contain the actual list of dictionaries
    that can be directly used without additional JSON parsing.
    """
    from app_graphql_api import server

    # Call the messages tool which returns List[Dict]
    result = await server._call_tool_mcp('messages', arguments={})

    # Result is a tuple of (content_list, raw_result)
    content_list, raw_result = result

    # The raw_result should have the actual data
    assert isinstance(raw_result, dict)
    assert 'result' in raw_result
    messages_result = raw_result['result']

    # Currently this is a list of JSON strings - this is the bug!
    # We're testing to capture the current (broken) behavior
    # After fix, this should be a list of dicts

    # Check that we got data back
    assert messages_result is not None
    assert len(messages_result) == 2

    # The issue: each item is a JSON string, not a dict
    # This test documents the expected behavior after the fix
    first_message = messages_result[0]

    # After fix: first_message should be a dict directly
    # Current bug: first_message is a JSON string
    if isinstance(first_message, str):
        # Current buggy behavior - items are JSON strings
        pytest.fail(
            f"List[Dict] items are returned as JSON strings instead of dicts. "
            f"Got: {type(first_message).__name__} = {first_message!r}"
        )

    # Expected behavior after fix
    assert isinstance(first_message, dict), \
        f"Expected dict, got {type(first_message).__name__}"
    assert 'role' in first_message
    assert 'content' in first_message
    assert first_message['role'] == 'user'
    assert first_message['content'] == 'Hello, how are you?'

    second_message = messages_result[1]
    assert isinstance(second_message, dict)
    assert second_message['role'] == 'assistant'
    assert second_message['content'] == "I'm good, thank you!"


@pytest.mark.asyncio
async def test_list_dict_in_text_content():
    """
    Test that TextContent contains properly formatted JSON for List[Dict].
    """
    from app_graphql_api import server
    from mcp.types import TextContent

    result = await server._call_tool_mcp('messages', arguments={})
    content_list, _ = result

    assert len(content_list) == 1
    text_content = content_list[0]
    assert isinstance(text_content, TextContent)

    # The text should be valid JSON that parses to a list of dicts
    parsed = json.loads(text_content.text)
    assert isinstance(parsed, list)
    assert len(parsed) == 2

    # Each item should be a dict (not a JSON string of a dict)
    for item in parsed:
        if isinstance(item, str):
            pytest.fail(
                f"TextContent contains double-encoded JSON. "
                f"Items should be dicts, not JSON strings. Got: {item!r}"
            )
        assert isinstance(item, dict), \
            f"Expected dict in parsed JSON, got {type(item).__name__}"
