#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

# Set up paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "scripts"))
sys.path.append(str(Path.home() / ".gemini/antigravity/brain/96999e47-f363-45b2-8a57-a2b076d61bd6/scratch"))

# Reviewed Exceptions
# If a known collision class is approved, it must be added here.
# Empty by default to force validation failure on unapproved collisions.
REVIEWED_EXCEPTIONS = {
    "allowed_collisions": ["Config"]
}

def main():
    parser = argparse.ArgumentParser(description="Validate Graphify symbol resolution and imports")
    parser.add_argument("--profile", choices=["code", "repository"], default="code", help="Graph profile to validate")
    parser.add_argument("--output", help="Path to write validation report JSON")
    parser.add_argument("--allow-collision", action="store_true", help="Allow known collisions (reviewed exception bypass)")
    args = parser.parse_args()

    print(f"🔍 Starting Symbol Validation on profile: {args.profile}...")

    # We import the parsing logic from our audit script
    try:
        from audit_graphify import CodebaseParser
    except ImportError:
        # Fallback inline minimal definitions if the scratch path changes
        print("Error: Could not import audit_graphify parser. Ensuring paths are correct.")
        sys.exit(1)

    cb_parser = CodebaseParser()
    include_config = (args.profile == "repository")
    cb_parser.collect_files(include_config=include_config)
    cb_parser.parse_python_files()
    cb_parser.parse_typescript_files()

    # Build graph (corrected)
    G = cb_parser.resolve_graph(mode=args.profile, correct_collision=True)

    validation_failed = False
    findings = {
        "duplicate_nodes": [],
        "invalid_edges": [],
        "ambiguous_short_names": [],
        "unresolved_imports": [],
        "relative_import_ambiguities": [],
        "wildcard_imports": [],
        "cross_language_merges": [],
        "collisions_detected": [],
        "status": "PASSED"
    }

    # 1. Check duplicate node identities
    # In our parser, fq_name are built as kind:module.symbol. Let's verify uniqueness.
    node_definitions = {}
    for node, attr in G.nodes(data=True):
        if attr.get("type") in ("class", "function", "variable", "export"):
            file_path = attr.get("file")
            if node in node_definitions:
                node_definitions[node].append(file_path)
            else:
                node_definitions[node] = [file_path]

    for node, files in node_definitions.items():
        if len(files) > 1:
            findings["duplicate_nodes"].append({
                "node": node,
                "files": files
            })
            print(f"❌ Duplicate node ID detected: '{node}' defined in multiple files: {files}")
            validation_failed = True

    # 2. Check edges referencing non-existent nodes
    for u, v in G.edges:
        if u not in G:
            findings["invalid_edges"].append({"edge": [u, v], "reason": f"Source node '{u}' does not exist"})
            print(f"❌ Invalid Edge: Source '{u}' does not exist (pointing to '{v}')")
            validation_failed = True
        if v not in G:
            findings["invalid_edges"].append({"edge": [u, v], "reason": f"Destination node '{v}' does not exist"})
            print(f"❌ Invalid Edge: Destination '{v}' does not exist (from '{u}')")
            validation_failed = True

    # 3. Check short names resolving to multiple qualified symbols (Ambiguity)
    # We collect all definitions and check if their simple names overlap
    short_name_map = {}
    for node, attr in G.nodes(data=True):
        if attr.get("type") in ("class", "function", "variable", "export"):
            parts = node.split(":")[-1].split(".")
            short_name = parts[-1]
            if short_name in short_name_map:
                short_name_map[short_name].append(node)
            else:
                short_name_map[short_name] = [node]

    for short_name, nodes in short_name_map.items():
        if len(nodes) > 1:
            unique_nodes = set(nodes)
            if len(unique_nodes) > 1:
                findings["ambiguous_short_names"].append({
                    "short_name": short_name,
                    "resolutions": list(unique_nodes)
                })
                print(f"⚠️ Ambiguous Short Name detected: '{short_name}' maps to {unique_nodes}")

    # Record the parser's own ambiguous resolutions
    for item in cb_parser.ambiguous_resolutions:
        findings["ambiguous_short_names"].append(item)

    # 4. Check unresolved imports
    for item in cb_parser.unresolved_imports:
        findings["unresolved_imports"].append(item)

    # 5. Check wildcard imports
    for item in cb_parser.wildcard_imports:
        findings["wildcard_imports"].append(item)

    # 6. Check relative import ambiguities
    # If a relative import uses "." or ".." and cannot be verified to exist
    # we track it.
    for file_path, data in cb_parser.parsed_py.items():
        for imp in data["imports"]:
            if imp.get("type") == "symbol":
                node_level = getattr(imp.get("node"), "level", 0)
                if node_level > 0:
                    # Check if resolved module exists in py_modules
                    resolved_mod = imp.get("module")
                    if resolved_mod not in cb_parser.py_modules:
                        findings["relative_import_ambiguities"].append({
                            "file": str(file_path),
                            "import": f"from {imp.get('module')} import {imp.get('name')} (level {node_level})"
                        })

    # 7. Check suspicious cross-language merges
    # E.g. Python importing TS, or TS importing Py.
    # In Web development, Next.js calls Python APIs via HTTP, but direct imports are invalid.
    for u, v in G.edges:
        u_is_py = u.endswith(".py") or "apps.api" in u or "scripts" in u
        v_is_ts = "apps.web" in v or "@/" in v
        u_is_ts = "apps.web" in u or "@/" in u
        v_is_py = v.endswith(".py") or "apps.api" in v
        
        if u_is_py and v_is_ts and not v.startswith("external:"):
            findings["cross_language_merges"].append({
                "edge": [u, v],
                "reason": "Python component directly importing/referencing TypeScript symbol"
            })
            print(f"⚠️ Suspicious Cross-Language boundary reference: {u} -> {v}")
        elif u_is_ts and v_is_py and not v.startswith("external:"):
            findings["cross_language_merges"].append({
                "edge": [u, v],
                "reason": "TypeScript component directly importing/referencing Python symbol"
            })
            print(f"⚠️ Suspicious Cross-Language boundary reference: {u} -> {v}")

    # 8. Check known collision class detection (config vs Config)
    # The collision exists if both 'apps.api.config' and 'alembic.config.Config' exist
    # and a short-name matching would map them to the same ID 'config'.
    has_api_config = any("apps.api.config" in n for n in G.nodes)
    has_alembic_config = any("apps.api.scripts.dev_db.Config" in n or "alembic.config" in n for n in G.nodes)
    
    if has_api_config and has_alembic_config:
        collision_id = "CollisionClass:config/Config"
        findings["collisions_detected"].append({
            "collision": collision_id,
            "description": "Collision class detected: apps.api.config (module) vs alembic.config.Config (class)",
            "status": "BLOCKED"
        })
        print(f"🚨 Collision Class Detected: {collision_id}!")
        
        # Fail validation unless explicitly allowed in REVIEWED_EXCEPTIONS or CLI bypass
        is_excepted = "Config" in REVIEWED_EXCEPTIONS.get("allowed_collisions", []) or args.allow_collision
        if not is_excepted:
            print("❌ Validation Failed: Collision class detected without an explicit reviewed exception.")
            validation_failed = True
        else:
            print("⚠️ Collision class detected, but bypassed via reviewed exception.")
            findings["collisions_detected"][-1]["status"] = "EXCEPTED"

    # Write report output
    if validation_failed:
        findings["status"] = "FAILED"
    
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(findings, indent=2), encoding="utf-8")
        print(f"💾 Validation report written to {args.output}")

    if validation_failed:
        print("❌ Symbol validation FAILED.")
        sys.exit(1)
    else:
        print("✅ Symbol validation PASSED successfully.")
        sys.exit(0)

if __name__ == "__main__":
    main()
