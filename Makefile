.PHONY: test lint evals run mcp hooks dev prod prod-down rollback approve-prod rehearse-rollback

test:
	uv run pytest

lint:
	uv run ruff check . && uv run ruff format --check .

evals:
	uv run python -m eval.offline

.PHONY: bands
bands:
	uv run python -m eval.bands

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

# Build the current commit's image and run it as prod. Needs a person's approval (make approve-prod).
prod:
	./scripts/prod-deploy.sh

# Stop prod and keep its images. The production gate asks agents for a person's approval first.
prod-down:
	docker compose -p erm --profile prod down

# A person approves one production change, in their own terminal. Agents are blocked from this.
approve-prod:
	./scripts/approve-prod.sh

# Return prod to the previous good image. Needs a person's approval (make approve-prod).
rollback:
	./scripts/rollback.sh

# Try a rollback in a separate Docker project. Real prod is not touched.
# Usage: make rehearse-rollback GOOD=<commit> NEW=<commit>
rehearse-rollback:
	./scripts/rehearse-rollback.sh $(GOOD) $(NEW)
