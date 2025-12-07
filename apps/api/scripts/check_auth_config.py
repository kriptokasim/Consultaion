#!/usr/bin/env python3
"""
Patchset 53.0: Auth Configuration Sanity Checker

Run this script on Render (or any environment) to verify auth settings.

Usage:
    python scripts/check_auth_config.py
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import settings


def main():
    print("=" * 60)
    print("AUTH CONFIGURATION SANITY CHECK")
    print("=" * 60)
    print()
    
    print(f"ENV: {settings.ENV}")
    print(f"IS_LOCAL_ENV: {settings.IS_LOCAL_ENV}")
    print()
    
    print("--- Web Origins ---")
    print(f"WEB_APP_ORIGIN: {settings.WEB_APP_ORIGIN}")
    print(f"CORS_ORIGINS: {settings.CORS_ORIGINS}")
    print()
    
    print("--- Cookie Settings ---")
    print(f"COOKIE_NAME: {settings.COOKIE_NAME}")
    print(f"COOKIE_SECURE: {settings.COOKIE_SECURE}")
    print(f"COOKIE_SAMESITE: {settings.COOKIE_SAMESITE}")
    print(f"COOKIE_DOMAIN: {settings.COOKIE_DOMAIN or '<not set (current host only)>'}")
    print(f"COOKIE_PATH: {settings.COOKIE_PATH}")
    print()
    
    print("--- CSRF Settings ---")
    print(f"ENABLE_CSRF: {settings.ENABLE_CSRF}")
    print(f"CSRF_COOKIE_NAME: {settings.CSRF_COOKIE_NAME}")
    print()
    
    print("--- Auth Debug ---")
    print(f"AUTH_DEBUG: {settings.AUTH_DEBUG}")
    print()
    
    # Validation warnings
    print("=" * 60)
    print("VALIDATION")
    print("=" * 60)
    print()
    
    issues = []
    
    if not settings.IS_LOCAL_ENV:
        # Production validations
        if not settings.COOKIE_SECURE:
            issues.append("⚠️  COOKIE_SECURE should be True in production")
        
        if settings.COOKIE_SAMESITE.lower() != "none":
            issues.append(f"⚠️  COOKIE_SAMESITE should be 'none' for cross-origin (Vercel + Render), got: {settings.COOKIE_SAMESITE}")
        
        if not settings.WEB_APP_ORIGIN:
            issues.append("⚠️  WEB_APP_ORIGIN is not set")
        
        if settings.WEB_APP_ORIGIN and settings.WEB_APP_ORIGIN not in settings.CORS_ORIGINS:
            issues.append(f"⚠️  WEB_APP_ORIGIN ({settings.WEB_APP_ORIGIN}) not in CORS_ORIGINS ({settings.CORS_ORIGINS})")
    
    if issues:
        for issue in issues:
            print(issue)
    else:
        print("✅ Configuration looks good!")
    
    print()
    
    # Return exit code based on issues
    return 1 if issues and not settings.IS_LOCAL_ENV else 0


if __name__ == "__main__":
    sys.exit(main())
