#!/usr/bin/env python3
"""
Test MCP communication with the running server
"""

import requests
import json

def test_mcp_communication():
    """Test direct MCP communication."""
    print("🧪 Testing MCP communication...")

    url = "http://localhost:8003/mcp"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    # Test tools/list
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text[:500]}...")

        if response.status_code == 200:
            # Parse SSE format
            response_text = response.text
            if response_text.startswith('event: message'):
                lines = response_text.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        json_data = line[6:]  # Remove 'data: ' prefix
                        result = json.loads(json_data)
                        if 'result' in result and 'tools' in result['result']:
                            tools = result['result']['tools']
                            print(f"✅ Found {len(tools)} tools:")
                            for tool in tools:
                                print(f"   • {tool['name']}: {tool['description']}")
                            return True
            print("❌ Could not parse SSE response")
            return False
        else:
            print(f"❌ Request failed with status {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False


def test_tool_call():
    """Test calling a specific tool."""
    print("\n🧪 Testing tool call...")

    url = "http://localhost:8003/mcp"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    # Test calling the hello tool
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {
            "name": "hello",
            "arguments": {"name": "World"}
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response Text: {response.text[:500]}...")

        if response.status_code == 200:
            # Parse SSE format
            response_text = response.text
            if response_text.startswith('event: message'):
                lines = response_text.split('\n')
                for line in lines:
                    if line.startswith('data: '):
                        json_data = line[6:]  # Remove 'data: ' prefix
                        result = json.loads(json_data)
                        if 'result' in result:
                            print(f"✅ Tool call result: {result['result']}")
                            return True
            print("❌ Could not parse SSE response")
            return False
        else:
            print(f"❌ Request failed with status {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Request failed: {e}")
        return False


if __name__ == "__main__":
    success1 = test_mcp_communication()
    success2 = test_tool_call()

    if success1 and success2:
        print("\n🎉 All MCP tests passed! The inspector should work now.")
    else:
        print("\n❌ Some tests failed.")