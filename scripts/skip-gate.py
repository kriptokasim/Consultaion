#!/usr/bin/env python3
import subprocess
import sys


def main():
    result = subprocess.run(
        ["pytest", "--collect-only", "-q"],
        capture_output=True,
        text=True,
        cwd="apps/api"
    )
    
    if "skipped" in result.stdout.lower() or "warnings" in result.stdout.lower() and "asyncio" in result.stdout:
        print("[!] SKIP GATE FAILED: Pytest output indicates skipped async tests or missing markers.")
        print(result.stdout)
        sys.exit(1)
        
    print("[+] SKIP GATE PASSED: All async tests are properly collected.")
    sys.exit(0)

if __name__ == "__main__":
    main()
