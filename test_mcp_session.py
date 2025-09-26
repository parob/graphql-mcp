#!/usr/bin/env python3
"""
Test MCP session initialization
"""

import requests
import json

def test_session_init():
    """Test MCP session initialization."""
    print("🧪 Testing MCP session initialization...")

    url = "http://localhost:8003/mcp"
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream"
    }

    # Test initialize
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {
                    "listChanged": False
                }
            },
            "clientInfo": {
                "name": "Test Client",
                "version": "1.0.0"
            }
        }
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        print(f"Initialize - Status Code: {response.status_code}")
        print(f"Response: {response.text[:200]}...")

        if response.status_code == 200:
            return True
        else:
            print(f"❌ Initialize failed with status {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Initialize failed: {e}")
        return False


if __name__ == "__main__":
    success = test_session_init()
    if success:
        print("✅ Session test completed")
    else:
        print("❌ Session test failed")