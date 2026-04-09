"""Structured data store — exact-value lookups from pre-extracted JSON files."""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"


class StructuredStore:
    """Loads pre-extracted JSON into memory for O(1) exact lookups.

    Uses plain Python dicts — no ORM overhead for read-only ground truth data.
    """

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self._data_dir = data_dir
        self._specs = self._load("specs.json")
        self._duty_cycles = self._load("duty_cycles.json")
        self._polarity = self._load("polarity.json")
        self._troubleshooting = self._load("troubleshooting.json")
        self._safety = self._load("safety.json")
        self._feed_rollers = self._load("feed_rollers.json")
        self._parts = self._load("parts.json")

    def _load(self, filename: str) -> dict:
        path = self._data_dir / filename
        if not path.exists():
            return {}
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    # --- Specifications ---

    def get_specs(self, process: str, voltage: str) -> dict | None:
        """Get specifications for a process at a given voltage."""
        process_data = self._specs.get(process)
        if not process_data:
            return None
        voltage_data = process_data.get(voltage)
        if not voltage_data:
            return None
        return voltage_data

    def get_all_specs(self, process: str) -> dict | None:
        """Get all specs for a process (both voltages + materials etc)."""
        return self._specs.get(process)

    # --- Duty Cycles ---

    def get_duty_cycle(self, process: str, voltage: str) -> dict | None:
        """Get duty cycle data for a process at a given voltage."""
        process_data = self._duty_cycles.get(process)
        if not process_data:
            return None
        return process_data.get(voltage)

    # --- Polarity ---

    def get_polarity(self, process: str) -> dict | None:
        """Get polarity and cable routing for a process."""
        return self._polarity.get(process)

    # --- Troubleshooting ---

    def get_troubleshooting(self, process_group: str) -> list[dict] | None:
        """Get all troubleshooting problems for a process group (mig_flux or tig_stick)."""
        group = self._troubleshooting.get(process_group)
        if not group:
            return None
        return group.get("problems")

    def search_troubleshooting(self, query: str, process_group: str) -> list[dict]:
        """Fuzzy match troubleshooting problems by keyword in problem name or causes."""
        problems = self.get_troubleshooting(process_group)
        if not problems:
            return []
        query_lower = query.lower()
        matches = []
        for problem in problems:
            # Check problem name
            if query_lower in problem["problem"].lower():
                matches.append(problem)
                continue
            # Check causes
            for cause in problem.get("causes", []):
                if query_lower in cause.lower():
                    matches.append(problem)
                    break
        return matches

    # --- Safety ---

    def get_safety(self, category: str) -> dict | None:
        """Get safety warnings for a category (electrical, fire, fumes_gas, etc)."""
        categories = self._safety.get("categories", {})
        return categories.get(category)

    def get_all_safety_categories(self) -> list[str]:
        """Get all available safety warning categories."""
        return list(self._safety.get("categories", {}).keys())

    # --- Feed Rollers ---

    def get_feed_roller(self, wire_type: str) -> dict | None:
        """Get feed roller info for a wire type (solid_core or flux_cored)."""
        return self._feed_rollers.get(wire_type)

    # --- Parts ---

    def get_parts(self) -> list[dict]:
        """Get full parts list."""
        return self._parts.get("parts", [])

    def search_parts(self, query: str) -> list[dict]:
        """Search parts by description keyword."""
        query_lower = query.lower()
        return [
            p for p in self.get_parts()
            if query_lower in p["description"].lower()
        ]


# Singleton instance — loaded once at import time
store = StructuredStore()
