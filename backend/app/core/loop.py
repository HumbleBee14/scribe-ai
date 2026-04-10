"""Custom uvicorn event-loop factory for Windows subprocess support.

Uvicorn's built-in asyncio loop factory returns SelectorEventLoop when
use_subprocess=True (i.e. --reload or --workers > 1). SelectorEventLoop
on Windows cannot create asyncio subprocesses, breaking the Claude Agent SDK.

This module provides a drop-in replacement that always returns
ProactorEventLoop on Windows, regardless of the use_subprocess flag.

Usage from CLI:
    uv run uvicorn app.main:app --reload --loop app.core.loop:proactor_loop_factory

Usage from Python:
    uvicorn.run("app.main:app", reload=True, loop="app.core.loop:proactor_loop_factory")
"""
from __future__ import annotations

import asyncio
import sys
from collections.abc import Callable


def proactor_loop_factory(use_subprocess: bool = False) -> Callable[[], asyncio.AbstractEventLoop]:
    """Return ProactorEventLoop on Windows, SelectorEventLoop elsewhere.

    Unlike uvicorn's built-in factory, this ALWAYS returns ProactorEventLoop
    on Windows, even when use_subprocess=True. ProactorEventLoop supports both
    asyncio subprocesses and regular I/O, making it safe for all scenarios.
    """
    if sys.platform == "win32":
        return asyncio.ProactorEventLoop
    return asyncio.SelectorEventLoop
