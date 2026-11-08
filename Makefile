.PHONY: test lint evals run desk excel mcp mcp-web hooks

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

evals:
	uv run python -m eval.offline

run:
	uv run streamlit run app/review.py

desk:
	uv run python -m app.desk.server

excel:
	ERM_DESK_PORT=3000 ERM_DESK_TLS=$$HOME/.office-addin-dev-certs uv run python -m app.desk.server

mcp-web:
	uv run python -m erm.mcp_remote

mcp:
	uv run python -m erm.mcp_server

# Installs the git pre-commit key scan, so commits made outside Claude Code are checked too.
hooks:
	ln -sf ../../scripts/pre-commit .git/hooks/pre-commit
	@echo "pre-commit key scan installed"
