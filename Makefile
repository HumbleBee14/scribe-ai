.PHONY: setup backend frontend dev test lint eval clean install-backend install-frontend

# ============================================================
# First-time setup: installs ALL dependencies (backend + frontend)
# Run this once after cloning.
# ============================================================
setup: .env install-backend install-frontend
	@echo ""
	@echo "================================================"
	@echo "  Setup complete!"
	@echo "  Start the app:"
	@echo "    make backend    (terminal 1)"
	@echo "    make frontend   (terminal 2)"
	@echo "================================================"

# Create .env from example if it doesn't exist
.env:
	cp .env.example .env
	@echo "Created .env from .env.example -- add your ANTHROPIC_API_KEY"

# ============================================================
# Install targets (run by setup, or manually if needed)
# ============================================================
install-backend:
	cd backend && (uv venv 2>/dev/null || true) && uv pip install -e ".[dev]"

install-frontend:
	cd frontend && npm install

# ============================================================
# Start backend / frontend (just starts, no install)
# ============================================================
backend:
	cd backend && uv run python run_server.py

frontend:
	cd frontend && npm run dev

# ============================================================
# Dev: instructions to start both
# ============================================================
dev:
	@echo "Run in two terminals:"
	@echo "  make backend"
	@echo "  make frontend"

# ============================================================
# Test / Lint / Eval
# ============================================================
test:
	cd backend && uv run pytest tests/ -q

lint:
	cd backend && uv run ruff check app/ tests/
	cd frontend && npm run lint

eval:
	cd backend && uv run python scripts/run_eval.py

# ============================================================
# Clean: remove installed dependencies (for fresh setup)
# ============================================================
clean:
	rm -rf backend/.venv frontend/node_modules
	@echo "Cleaned. Run 'make setup' to reinstall."
