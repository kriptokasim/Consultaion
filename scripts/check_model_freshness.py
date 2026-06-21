#!/usr/bin/env python3
"""
Model Freshness Checker

Checks the MODEL_MAP for models that haven't been verified recently.
Validates cost_class consistency and missing metadata.
"""
import argparse
import datetime
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from apps.api.model_gateway.model_map import MODEL_MAP, MODEL_ALIASES

def check_freshness(strict: bool = False) -> int:
    exit_code = 0
    warnings = 0
    
    now = datetime.datetime.now()
    threshold = now - datetime.timedelta(days=90)
    
    print("Checking model freshness and metadata...")
    print(f"Total canonical models: {len(MODEL_MAP)}")
    print(f"Total aliases: {len(MODEL_ALIASES)}\n")
    
    for key, data in MODEL_MAP.items():
        if data.get("deprecated"):
            continue
            
        last_verified = data.get("last_verified_at")
        if not last_verified:
            print(f"⚠️  {key}: Missing last_verified_at")
            warnings += 1
            if strict: exit_code = 1
            continue
            
        try:
            verified_date = datetime.datetime.strptime(last_verified, "%Y-%m-%d")
            if verified_date < threshold:
                print(f"⚠️  {key}: Verification stale ({last_verified}) - > 90 days ago")
                warnings += 1
                if strict: exit_code = 1
        except ValueError:
            print(f"⚠️  {key}: Invalid date format for last_verified_at: {last_verified}")
            warnings += 1
            if strict: exit_code = 1
            
        # Check free tier specific metadata
        if data.get("cost_class") == "free":
            if not data.get("free_tier_verified_at"):
                print(f"⚠️  {key}: Free model missing free_tier_verified_at")
                warnings += 1
                if strict: exit_code = 1
            if not data.get("free_tier_source"):
                print(f"⚠️  {key}: Free model missing free_tier_source")
                warnings += 1
                if strict: exit_code = 1
                
        # Validate cost_class enum
        if data.get("cost_class") not in ("free", "cheap", "paid", "unknown"):
            print(f"⚠️  {key}: Invalid cost_class: {data.get('cost_class')}")
            warnings += 1
            if strict: exit_code = 1

    print(f"\nScan complete. Warnings found: {warnings}")
    if warnings == 0:
        print("✅ All models are fresh and correctly configured.")
        
    return exit_code

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check model map freshness")
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero code on warnings")
    args = parser.parse_args()
    
    sys.exit(check_freshness(args.strict))
