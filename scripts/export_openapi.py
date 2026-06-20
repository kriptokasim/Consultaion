import json
import os
import sys

# Add apps/api to path so main and other modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "apps", "api")))

# Ensure environment vars are set so app doesn't fail fast on missing keys
os.environ["ENV"] = "local"
os.environ["DATABASE_URL"] = "sqlite:///dev.db"
os.environ["JWT_SECRET"] = "change_me_in_prod"

from main import app


def export_spec():
    openapi_schema = app.openapi()
    target_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs"))
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(target_dir, "openapi.json")
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(openapi_schema, f, indent=2)
    print(f"Exported OpenAPI spec to {target_path}")

if __name__ == "__main__":
    export_spec()
