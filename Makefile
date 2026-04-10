.PHONY: backend frontend dev setup test lint eval

# Start backend
backend:
	cd backend && uv run python run_server.py

# Start frontend
frontend:
	cd frontend && npm run dev

# Start both (run in separate terminals)
dev:
	@echo "Run in two terminals:"
	@echo "  make backend"
	@echo "  make frontend"

# First-time setup
setup:
	cd backend && uv venv && uv pip install -e ".[dev]"
	cd frontend && npm install

# Run tests
test:
	cd backend && uv run pytest tests/ -q

# Lint
lint:
	cd backend && uv run ruff check app/ tests/
	cd frontend && npm run lint

# Run eval suite (needs API key)
eval:
	cd backend && uv run python scripts/run_eval.py
