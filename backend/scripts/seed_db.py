#!/usr/bin/env python3
"""Seed the SQLite database from on-disk product manifests.

Run this once after cloning, or after adding new seeded products:
    python -m scripts.seed_db

Safe to run multiple times (skips existing products).
"""
import sys
from pathlib import Path

# Ensure backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import init_db
from app.core.seed import seed_from_disk


def main() -> None:
    init_db()
    count = seed_from_disk()
    print(f"Seeded {count} product(s) into local.db")


if __name__ == "__main__":
    main()
