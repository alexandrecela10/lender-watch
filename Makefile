.PHONY: test lint evals run mcp hooks dev

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

evals:
	uv run python -m eval.offline

run:
	uv run streamlit run app/review.py

mcp:
	uv run python -m erm.mcp_server

# Installs the git pre-commit key scan, so commits made outside Claude Code are checked too.
hooks:
	ln -sf ../../scripts/pre-commit .git/hooks/pre-commit
	@echo "pre-commit key scan installed"

# The review app in Docker, with live code reload. Needs no key.
dev:
	docker compose --profile dev up --build
