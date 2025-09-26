#!/usr/bin/env python3
"""
Test simple MCP communication without session management
"""

import requests
import json

def test_direct_tools_list():
    """Test tools/list directly without initialization."""
    print("🧪 Testing direct tools/list...")

    url = "http://localhost:8003/mcp"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    # Test tools/list directly
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        return response.status_code == 200

    except Exception as e:
        print(f"❌ Failed: {e}")
        return False


if __name__ == "__main__":
    success = test_direct_tools_list()
    if success:
        print("✅ Direct tools/list works - no session needed!")
    else:
        print("❌ Direct tools/list failed")