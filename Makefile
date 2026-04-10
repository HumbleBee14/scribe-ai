.PHONY: backend frontend dev setup test lint eval

# Start backend (auto-installs if needed)
backend: backend/.venv
	cd backend && uv run python run_server.py

# Start frontend (auto-installs if needed)
frontend: frontend/node_modules
	cd frontend && npm run dev

# Start both (run in separate terminals)
dev:
	@echo "Run in two terminals:"
	@echo "  make backend"
	@echo "  make frontend"

# First-time setup (explicit)
setup: backend/.venv frontend/node_modules

backend/.venv:
	cd backend && uv venv && uv pip install -e ".[dev]"

frontend/node_modules:
	cd frontend && npm install

# Run tests
test: backend/.venv
	cd backend && uv run pytest tests/ -q

# Lint
lint: backend/.venv frontend/node_modules
	cd backend && uv run ruff check app/ tests/
	cd frontend && npm run lint

# Run eval suite (needs API key)
eval: backend/.venv
	cd backend && uv run python scripts/run_eval.py
