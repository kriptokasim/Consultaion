.PHONY: api-dev-db-migrate api-dev-db-reset api-dev-db-verify api-dev-db-seed export-openapi

api-dev-db-migrate:
	cd apps/api && . .venv/bin/activate && python -m scripts.dev_db migrate

api-dev-db-reset:
	cd apps/api && . .venv/bin/activate && python -m scripts.dev_db reset-and-migrate

api-dev-db-verify:
	cd apps/api && . .venv/bin/activate && python -m scripts.dev_db verify

api-dev-db-seed:
	cd apps/api && . .venv/bin/activate && python -m scripts.dev_db seed-demo

export-openapi:
	cd apps/api && . .venv/bin/activate && python ../../scripts/export_openapi.py

