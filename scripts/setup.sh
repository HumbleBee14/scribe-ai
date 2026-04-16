#!/usr/bin/env bash
set -e

echo "Setting up Scribe AI..."

# Backend
echo "Setting up backend (uv)..."
cd backend
uv venv --quiet 2>/dev/null || true
uv pip install -e ".[dev]" --quiet
cd ..

# Frontend
echo "Setting up frontend (npm)..."
cd frontend
npm install --silent
cd ..

echo ""
echo "Setup complete! To run:"
echo "  Backend:  cd backend && uv run python run_server.py --port 8000"
echo "  Frontend: cd frontend && npm run dev"
echo ""
