
files = [
    "/home/durmusahm/Consultaion/apps/api/orchestration/analysis.py",
    "/home/durmusahm/Consultaion/apps/api/parliament/engine.py",
    "/home/durmusahm/Consultaion/apps/api/reporting/model_evaluator.py",
    "/home/durmusahm/Consultaion/apps/api/reporting/synthesis_critic.py",
    "/home/durmusahm/Consultaion/apps/api/reporting/report_builder.py",
    "/home/durmusahm/Consultaion/apps/api/reporting/claim_contradiction.py",
    "/home/durmusahm/Consultaion/apps/api/reporting/synthesizer.py",
    "/home/durmusahm/Consultaion/apps/api/worker/arena_tasks.py",
]

for filepath in files:
    with open(filepath, "r") as f:
        content = f.read()

    # Add import if not present
    if "from utils.json_utils import extract_and_parse_json" not in content:
        # insert after "import json" or at top
        if "import json" in content:
            content = content.replace("import json", "import json\nfrom utils.json_utils import extract_and_parse_json")
        else:
            content = "from utils.json_utils import extract_and_parse_json\n" + content

    # Custom regex replacement per file logic
    
    with open(filepath, "w") as f:
        f.write(content)
        
    print(f"Added import to {filepath}")
