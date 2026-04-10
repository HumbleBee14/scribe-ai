"""Structured data store — exact-value lookups from pre-extracted JSON files."""
from __future__ import annotations

import json
import logging
from pathlib import Path

from app.packs.registry import get_active_product

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent / "data"

# Files that MUST exist for the system to function correctly.
# Missing any of these means the agent cannot answer exact-data questions.
REQUIRED_FILES = [
    "specs.json",
    "duty_cycles.json",
    "polarity.json",
    "troubleshooting.json",
    "safety.json",
]

# Files that are useful but not critical — degrade gracefully if missing.
OPTIONAL_FILES = [
    "feed_rollers.json",
    "parts.json",
]


class StructuredStoreError(Exception):
    """Raised when required knowledge files are missing or corrupt."""


class StructuredStore:
    """Loads pre-extracted JSON into memory for O(1) exact lookups.

    Uses plain Python dicts — no ORM overhead for read-only ground truth data.
    Fails fast on missing required files to prevent silent degradation.
    """

    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self._data_dir = data_dir
        self._loaded_files: list[str] = []
        self._missing_required: list[str] = []
        self._missing_optional: list[str] = []

        self._specs = self._load_required("specs.json")
        self._duty_cycles = self._load_required("duty_cycles.json")
        self._polarity = self._load_required("polarity.json")
        self._troubleshooting = self._load_required("troubleshooting.json")
        self._safety = self._load_required("safety.json")
        self._feed_rollers = self._load_optional("feed_rollers.json")
        self._parts = self._load_optional("parts.json")

    def _load_required(self, filename: str) -> dict:
        """Load a required JSON file. Raises on missing/corrupt."""
        path = self._data_dir / filename
        if not path.exists():
            self._missing_required.append(filename)
            raise StructuredStoreError(
                f"Required knowledge file missing: {path}. "
                f"Run the ingestion pipeline first."
            )
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._loaded_files.append(filename)
            return data
        except (json.JSONDecodeError, OSError) as e:
            raise StructuredStoreError(
                f"Failed to load {path}: {e}"
            ) from e

    def _load_optional(self, filename: str) -> dict:
        """Load an optional JSON file. Logs warning on missing, returns empty dict."""
        path = self._data_dir / filename
        if not path.exists():
            logger.warning("Optional knowledge file missing: %s", path)
            self._missing_optional.append(filename)
            return {}
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self._loaded_files.append(filename)
            return data
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load optional file %s: %s", path, e)
            return {}

    def health_check(self) -> dict:
        """Return startup health status for diagnostics.

        healthy = True when all REQUIRED files are loaded.
        Missing optional files are reported but don't fail the health check.
        """
        return {
            "loaded": self._loaded_files,
            "missing_required": self._missing_required,
            "missing_optional": self._missing_optional,
            "data_dir": str(self._data_dir),
            "healthy": len(self._missing_required) == 0,
        }

    # --- Specifications ---

    def get_specs(self, process: str, voltage: str) -> dict | None:
        """Get full specifications for a process at a given voltage.

        Returns voltage-specific specs merged with process-level metadata
        (weldable_materials, wire capacity, etc) so callers get the complete picture.
        """
        process_data = self._specs.get(process)
        if not process_data:
            return None
        voltage_data = process_data.get(voltage)
        if not voltage_data:
            return None
        # Merge process-level metadata into the voltage-specific result
        result = dict(voltage_data)
        for key in ("weldable_materials", "welding_wire_capacity", "wire_speed",
                     "wire_spool_capacity", "_note"):
            if key in process_data:
                result[key] = process_data[key]
        return result

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
        """Get all troubleshooting problems for a process group."""
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
            if query_lower in problem["problem"].lower():
                matches.append(problem)
                continue
            for cause in problem.get("causes", []):
                if query_lower in cause.lower():
                    matches.append(problem)
                    break
        return matches

    # --- Safety ---

    def get_safety(self, category: str) -> dict | None:
        """Get safety warnings for a category."""
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


# ---------------------------------------------------------------------------
# Factory — construct explicitly during app startup, not at import time.
# Keyed by data_dir so different document packs get separate stores.
# ---------------------------------------------------------------------------

_stores: dict[str, StructuredStore] = {}


def get_store(data_dir: Path | None = None) -> StructuredStore:
    """Get or create a StructuredStore for the given data directory.

    Keyed by resolved path, so different document packs get separate instances.
    Call this during app startup (lifespan) or in request handlers,
    not at module import time.
    """
    if data_dir is None:
        data_dir = get_active_product().structured_dir
    key = str(data_dir.resolve())
    if key not in _stores:
        _stores[key] = StructuredStore(data_dir)
    return _stores[key]


def reset_store() -> None:
    """Reset all store instances — used in tests."""
    _stores.clear()
