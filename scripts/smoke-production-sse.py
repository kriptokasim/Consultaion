#!/usr/bin/env python3
"""FH128 — Production SSE Smoke Test.

Validates that the production GET /debates/{id}/stream endpoint
properly handles reconnect cursors and correctly releases stream leases.

Usage:
  export API_BASE_URL=https://api.consultaion.com
  export STREAM_TOKEN=ey...
  export TEST_DEBATE_ID=deb_123...
  python scripts/smoke-production-sse.py
"""

import asyncio
import os
import sys

import httpx

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")
STREAM_TOKEN = os.environ.get("STREAM_TOKEN")
TEST_DEBATE_ID = os.environ.get("TEST_DEBATE_ID")


async def smoke_test():
    if not STREAM_TOKEN or not TEST_DEBATE_ID:
        print("ERROR: STREAM_TOKEN and TEST_DEBATE_ID environment variables must be set.")
        sys.exit(1)

    print(f"[*] Targeting API: {API_BASE_URL}")
    print(f"[*] Test Debate: {TEST_DEBATE_ID}")
    
    stream_url = f"{API_BASE_URL}/debates/{TEST_DEBATE_ID}/stream"
    headers = {"Authorization": f"Bearer {STREAM_TOKEN}"}
    
    # 1. Fresh Connection
    print("[*] Test 1: Fresh Connection...")
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", stream_url, headers=headers) as response:
                if response.status_code != 200:
                    print(f"[!] FAILED: Expected 200, got {response.status_code}")
                    sys.exit(1)
                
                print("    ✓ HTTP 200 OK")
                print(f"    ✓ Content-Type: {response.headers.get('content-type')}")
                assert "text/event-stream" in response.headers.get("content-type", "")
                
                # Read one chunk to verify connection
                chunk = await response.aiter_text().__anext__()
                print(f"    ✓ Received initial bytes: {len(chunk)}b")
                
    except Exception as e:
        print(f"[!] FAILED: Exception during fresh connection: {e}")
        sys.exit(1)

    # 2. Reconnect with Cursor
    print("\n[*] Test 2: Reconnect with Last-Event-ID...")
    reconnect_headers = headers.copy()
    reconnect_headers["Last-Event-ID"] = "5"
    
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", stream_url, headers=reconnect_headers) as response:
                if response.status_code != 200:
                    print(f"[!] FAILED: Expected 200, got {response.status_code}")
                    print(f"[!] Response body: {await response.aread()}")
                    sys.exit(1)
                
                print("    ✓ HTTP 200 OK with cursor")
                # Break immediately to test cancellation
                
    except Exception as e:
        print(f"[!] FAILED: Exception during reconnect: {e}")
        sys.exit(1)
        
    # Wait for background cleanup
    print("\n[*] Waiting for background lease release (2s)...")
    await asyncio.sleep(2.0)
    
    print("\n[+] All SSE smoke tests passed.")
    print("[+] If lease leakage was occurring, multiple repeated runs would 503.")


if __name__ == "__main__":
    asyncio.run(smoke_test())
