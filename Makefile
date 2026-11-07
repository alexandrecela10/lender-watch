.PHONY: test lint evals run mcp

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

# Stub: exits 1 until eval/offline.py lands in M4.
evals:
	uv run python -m eval.offline

run:
	uv run streamlit run app/review.py

mcp:
	uv run python -m erm.mcp_server
