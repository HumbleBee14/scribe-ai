"""Windows-safe uvicorn launcher.

On Windows, uvicorn's default loop selection with --reload uses
SelectorEventLoop, which does NOT support asyncio subprocesses.
The Claude Agent SDK spawns a subprocess internally via
asyncio.create_subprocess_exec, causing:

    NotImplementedError  (from asyncio/base_events.py _make_subprocess_transport)

Fix: pass loop="none" so uvicorn does not override the event loop factory.
Python 3.8+ on Windows defaults to ProactorEventLoop, which supports
subprocesses. With loop="none", asyncio.run() uses the default policy and
creates a ProactorEventLoop in every process (including reload child processes).

Usage (replaces the old CLI command):
    uv run python run_server.py
    uv run python run_server.py --port 8001
    uv run python run_server.py --no-reload
"""
from __future__ import annotations


def main() -> None:
    import argparse

    import uvicorn

    parser = argparse.ArgumentParser(description="Run the Prox Agent backend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true", default=True)
    parser.add_argument("--no-reload", dest="reload", action="store_false")
    args = parser.parse_args()

    # loop="none" tells uvicorn NOT to supply a loop_factory to asyncio.run().
    # On Windows, asyncio.run() then uses the default WindowsProactorEventLoopPolicy,
    # creating a ProactorEventLoop that supports asyncio.create_subprocess_exec().
    #
    # The default loop="auto" resolves to SelectorEventLoop when --reload is set
    # (use_subprocess=True), which breaks subprocess creation on Windows.
    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        loop="none",
    )


if __name__ == "__main__":
    main()
