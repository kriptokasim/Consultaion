#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import networkx as nx
import networkx.algorithms.community as nx_comm

# Set up paths
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT / "scripts"))

def generate_svg_overview(G, output_path):
    # A simple, clean, lightweight SVG showing communities/subsystems and their sizes
    sub_nodes = [n for n in G.nodes if not n.startswith("external:")]
    sub_G = G.subgraph(sub_nodes).to_undirected()
    
    # Run community detection
    try:
        communities = list(nx_comm.louvain_communities(sub_G))
    except Exception:
        communities = [set(sub_nodes)]

    # We draw an SVG mapping the communities as circles
    svg_width = 800
    svg_height = 600
    
    svg_content = [
        f'<svg width="{svg_width}" height="{svg_height}" viewBox="0 0 {svg_width} {svg_height}" xmlns="http://www.w3.org/2000/svg" style="background:#0b0f19; font-family:sans-serif;">',
        "<style>",
        "  .title { fill: #f3f4f6; font-size: 20px; font-weight: bold; }",
        "  .subtitle { fill: #9ca3af; font-size: 12px; }",
        "  .comm-circle { fill: #1e293b; stroke: #3b82f6; stroke-width: 2px; opacity: 0.85; transition: all 0.3s; }",
        "  .comm-text { fill: #f3f4f6; font-size: 11px; font-weight: 600; text-anchor: middle; }",
        "  .comm-sub { fill: #9ca3af; font-size: 9px; text-anchor: middle; }",
        "</style>",
        '<text x="40" y="50" class="title">Consultaion Architecture Communities Map</text>',
        f'<text x="40" y="75" class="subtitle">Visual representation of {len(communities)} clustered code components (excluding external packages)</text>'
    ]

    import math
    num_comm = len(communities)
    if num_comm > 0:
        # Arrange communities in a grid or circle
        cols = int(math.ceil(math.sqrt(num_comm)))
        rows = int(math.ceil(num_comm / cols))
        
        dx = (svg_width - 80) / cols
        dy = (svg_height - 120) / rows
        
        for idx, comm in enumerate(communities):
            row = idx // cols
            col = idx % cols
            cx = 60 + col * dx + dx / 2
            cy = 120 + row * dy + dy / 2
            
            # Radius proportional to community size
            size = len(comm)
            radius = min(dx, dy) * 0.45
            radius = max(30, min(radius, 10 + math.sqrt(size) * 15))
            
            # Get primary modules in the community
            modules = [n.split(":")[-1] for n in comm if n.startswith("module:")]
            main_label = modules[0].split(".")[-1] if modules else f"Comm {idx}"
            
            svg_content.append(f'  <circle cx="{cx}" cy="{cy}" r="{radius}" class="comm-circle" />')
            svg_content.append(f'  <text x="{cx}" y="{cy - 2}" class="comm-text">{main_label}</text>')
            svg_content.append(f'  <text x="{cx}" y="{cy + 12}" class="comm-sub">{size} nodes</text>')
            
    svg_content.append("</svg>")
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(svg_content))

def main():
    parser = argparse.ArgumentParser(description="Generate Graphify reports and viewer data")
    parser.add_argument("--profile", choices=["code", "repository"], required=True, help="Graph profile to build")
    parser.add_argument("--sha", default="unknown", help="Repository Git SHA")
    parser.add_argument("--version", default="0.8.42", help="Graphify Version")
    parser.add_argument("--outdir", required=True, help="Output folder")
    parser.add_argument("--allow-collision", action="store_true", help="Allow known collisions")
    args = parser.parse_args()

    out_root = Path(args.outdir)
    reports_dir = out_root / "reports"
    viewer_dir = out_root / "viewer"
    viewer_data_dir = viewer_dir / "data"

    # Create directories
    reports_dir.mkdir(parents=True, exist_ok=True)
    viewer_data_dir.mkdir(parents=True, exist_ok=True)

    try:
        from audit_graphify import CodebaseParser
    except ImportError:
        print("Error: Could not import audit_graphify parser.")
        sys.exit(1)

    cb_parser = CodebaseParser()
    include_config = (args.profile == "repository")
    cb_parser.collect_files(include_config=include_config)
    cb_parser.parse_python_files()
    cb_parser.parse_typescript_files()

    # Build graph
    G = cb_parser.resolve_graph(mode=args.profile, correct_collision=True)

    # 1. Run Louvain clustering to map communities
    sub_nodes = [n for n in G.nodes if not n.startswith("external:")]
    sub_G = G.subgraph(sub_nodes).to_undirected()
    
    community_map = {}
    try:
        communities = list(nx_comm.louvain_communities(sub_G))
        for idx, comm in enumerate(communities):
            for node in comm:
                community_map[node] = idx
    except Exception as e:
        print(f"Clustering warning: {e}")

    # Inject communities back into node attributes
    for node in G.nodes:
        if node in community_map:
            G.nodes[node]["community"] = community_map[node]
        else:
            G.nodes[node]["community"] = -1

    # Save primary graph.json
    graph_data = nx.node_link_data(G)
    with open(out_root / "graph.json", "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)
    with open(viewer_data_dir / "graph.json", "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2)

    # Compute Centrality (undirected, internal)
    G_undir = G.to_undirected()
    try:
        deg = nx.degree_centrality(G_undir)
        bet = nx.betweenness_centrality(G_undir)
        
        # Filter external
        deg_filtered = {n: val for n, val in deg.items() if not n.startswith("external:")}
        bet_filtered = {n: val for n, val in bet.items() if not n.startswith("external:")}
    except Exception as e:
        deg_filtered = {n: 0.0 for n in G.nodes}
        bet_filtered = {n: 0.0 for n in G.nodes}

    # 2. Generate Reports
    
    # Fan-In (in-degree)
    in_deg = G.in_degree()
    fan_in_list = sorted([{"node": n, "value": val} for n, val in in_deg if not n.startswith("external:")], key=lambda x: x["value"], reverse=True)
    with open(reports_dir / "top-fan-in.json", "w", encoding="utf-8") as f:
        json.dump(fan_in_list, f, indent=2)
    with open(viewer_data_dir / "top-fan-in.json", "w", encoding="utf-8") as f:
        json.dump(fan_in_list, f, indent=2)

    # Fan-Out (out-degree)
    out_deg = G.out_degree()
    fan_out_list = sorted([{"node": n, "value": val} for n, val in out_deg if not n.startswith("external:")], key=lambda x: x["value"], reverse=True)
    with open(reports_dir / "top-fan-out.json", "w", encoding="utf-8") as f:
        json.dump(fan_out_list, f, indent=2)
    with open(viewer_data_dir / "top-fan-out.json", "w", encoding="utf-8") as f:
        json.dump(fan_out_list, f, indent=2)

    # Strongly Connected Components & Cycles
    sccs = list(nx.strongly_connected_components(G.subgraph(sub_nodes)))
    scc_list = sorted([{"size": len(scc), "nodes": list(scc)} for scc in sccs], key=lambda x: x["size"], reverse=True)
    
    with open(reports_dir / "strongly-connected-components.json", "w", encoding="utf-8") as f:
        json.dump(scc_list, f, indent=2)
    with open(viewer_data_dir / "strongly-connected-components.json", "w", encoding="utf-8") as f:
        json.dump(scc_list, f, indent=2)

    cycles_list = [item for item in scc_list if item["size"] > 1]
    with open(reports_dir / "dependency-cycles.json", "w", encoding="utf-8") as f:
        json.dump(cycles_list, f, indent=2)
    with open(viewer_data_dir / "dependency-cycles.json", "w", encoding="utf-8") as f:
        json.dump(cycles_list, f, indent=2)

    # Ambiguous Symbols
    with open(reports_dir / "ambiguous-symbols.json", "w", encoding="utf-8") as f:
        json.dump(cb_parser.ambiguous_resolutions, f, indent=2)
    with open(viewer_data_dir / "ambiguous-symbols.json", "w", encoding="utf-8") as f:
        json.dump(cb_parser.ambiguous_resolutions, f, indent=2)

    # Unresolved Imports
    with open(reports_dir / "unresolved-imports.json", "w", encoding="utf-8") as f:
        json.dump(cb_parser.unresolved_imports, f, indent=2)
    with open(viewer_data_dir / "unresolved-imports.json", "w", encoding="utf-8") as f:
        json.dump(cb_parser.unresolved_imports, f, indent=2)

    # Orphans (Degree = 0, exclude external)
    orphans = sorted([{"node": n, "value": 0} for n in G.nodes if not n.startswith("external:") and G.degree(n) == 0], key=lambda x: x["node"])
    with open(reports_dir / "orphan-symbols.json", "w", encoding="utf-8") as f:
        json.dump(orphans, f, indent=2)
    with open(viewer_data_dir / "orphan-symbols.json", "w", encoding="utf-8") as f:
        json.dump(orphans, f, indent=2)

    # Boundary Violations
    violations = []
    for u, v in G.edges:
        is_u_web = "apps.web" in u or "apps/web" in u or "config:apps/web" in u
        is_v_api = "apps.api" in v or "apps/api" in v
        if is_u_web and is_v_api and not v.startswith("external:"):
            violations.append({"source": u, "target": v, "reason": "Frontend directly referencing backend symbol/module"})
            
        is_u_api = "apps.api" in u or "apps/api" in u
        is_v_web = "apps.web" in v or "apps/web" in v
        if is_u_api and is_v_web and not v.startswith("external:"):
            violations.append({"source": u, "target": v, "reason": "Backend directly referencing frontend symbol/module"})
            
    with open(reports_dir / "boundary-violations.json", "w", encoding="utf-8") as f:
        json.dump(violations, f, indent=2)
    with open(viewer_data_dir / "boundary-violations.json", "w", encoding="utf-8") as f:
        json.dump(violations, f, indent=2)

    # Architecture Overview SVG
    generate_svg_overview(G, reports_dir / "architecture-overview.svg")

    # Build Metadata
    from datetime import datetime
    
    # Run symbol validation status check
    # Fail status if there is a collision and we don't have bypass
    has_api_config = any("apps.api.config" in n for n in G.nodes)
    has_alembic_config = any("apps.api.scripts.dev_db.Config" in n or "alembic.config" in n for n in G.nodes)
    
    validation_status = "PASSED"
    if has_api_config and has_alembic_config and not args.allow_collision:
        validation_status = "FAILED"

    metadata = {
        "repository_sha": args.sha,
        "graphify_version": args.version,
        "build_timestamp": datetime.utcnow().isoformat() + "Z",
        "graph_profile": args.profile,
        "ignore_profile": f"{args.profile} Graph Profile",
        "node_count": len(G.nodes),
        "edge_count": len(G.edges),
        "community_count": len(set(community_map.values())),
        "ambiguous_symbol_count": len(cb_parser.ambiguous_resolutions),
        "unresolved_import_count": len(cb_parser.unresolved_imports),
        "strongly_connected_component_count": len(sccs),
        "build_command": f"./scripts/build-architecture-graph.sh --profile {args.profile}",
        "validation_status": validation_status
    }

    with open(reports_dir / "build-metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    with open(viewer_data_dir / "build-metadata.json", "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print("📊 Profile generation complete.")
    print(f"   Nodes: {len(G.nodes)}, Edges: {len(G.edges)}, Communities: {metadata['community_count']}")

if __name__ == "__main__":
    main()
