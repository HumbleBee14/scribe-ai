#!/usr/bin/env bash
set -e

echo "Starting Prox Multimodal Agent (dev mode)..."

# Backend
echo "Starting backend..."
cd backend
uv run uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Frontend
echo "Starting frontend..."
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

echo ""
echo "Backend:  http://localhost:8000"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl+C to stop both services."

trap "kill $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT
wait
