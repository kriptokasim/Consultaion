#!/usr/bin/env python3
"""
Changelog Sync Script

Reads the docs/release-manifest.json and generates docs/STATE.md and a
CHANGELOG.md entry for the current patchset.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
MANIFEST_PATH = ROOT / "docs" / "release-manifest.json"
STATE_MD_PATH = ROOT / "docs" / "STATE.md"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"


def get_manifest():
    if not MANIFEST_PATH.exists():
        print(f"Error: {MANIFEST_PATH} not found.")
        sys.exit(1)
    with open(MANIFEST_PATH, "r") as f:
        return json.load(f)


def update_state_md(manifest):
    content = f"""# System State
*Generated from release-manifest.json*

**Patchset**: {manifest['patchset']}
**Verified Code SHA**: `{manifest['verified_code_sha']}`
**Production Readiness**: `{manifest['production_readiness']}`

### Tracks
**Closed**: {", ".join(manifest['closed_tracks']) if manifest['closed_tracks'] else "None"}
**Open**: {", ".join(manifest['open_tracks']) if manifest['open_tracks'] else "None"}
"""
    with open(STATE_MD_PATH, "w") as f:
        f.write(content)
    print(f"Updated {STATE_MD_PATH.name}")


def update_changelog(manifest):
    if not CHANGELOG_PATH.exists():
        print(f"Error: {CHANGELOG_PATH} not found.")
        sys.exit(1)
        
    with open(CHANGELOG_PATH, "r") as f:
        content = f.read()
        
    patchset_num = manifest["patchset"]
    header = f"## Patchset {patchset_num}"
    
    # Check if this patchset is already in the changelog (idempotent)
    if header in content:
        print(f"Changelog already contains {header}. Skipping append.")
        return
        
    new_entry = f"""{header}
- **Production Readiness**: `{manifest['production_readiness']}`
- **Verified Code SHA**: `{manifest['verified_code_sha']}`
- Closed Tracks: {", ".join(manifest['closed_tracks'])}
- Open Tracks: {", ".join(manifest['open_tracks'])}
"""

    # Insert after the main title (# Changelog)
    lines = content.split("\n")
    insert_idx = 0
    for i, line in enumerate(lines):
        if line.startswith("# Changelog"):
            insert_idx = i + 1
            break
            
    # Also skip empty lines after the title
    while insert_idx < len(lines) and lines[insert_idx].strip() == "":
        insert_idx += 1
        
    lines.insert(insert_idx, "\n" + new_entry)
    
    with open(CHANGELOG_PATH, "w") as f:
        f.write("\n".join(lines))
    print(f"Updated {CHANGELOG_PATH.name}")


if __name__ == "__main__":
    manifest = get_manifest()
    update_state_md(manifest)
    update_changelog(manifest)
    print("Sync complete.")
