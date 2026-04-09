"""Deterministic validation for exact technical answers.

Compares proposed answer values against structured ground truth.
Rejects mismatches before they reach the user.
"""
from __future__ import annotations


def validate_exact_answer(
    query_type: str,
    proposed: dict,
    ground_truth: dict,
) -> dict:
    """Validate that a proposed exact answer matches ground truth.

    Returns:
        {"valid": True/False, "reason": str, "mismatches": list}
    """
    mismatches: list[str] = []

    if query_type == "duty_cycle":
        for key in ("duty_cycle_percent", "amperage", "weld_minutes", "rest_minutes"):
            if key in proposed and key in ground_truth:
                if proposed[key] != ground_truth[key]:
                    mismatches.append(
                        f"{key}: proposed {proposed[key]}, expected {ground_truth[key]}"
                    )
        return {
            "valid": len(mismatches) == 0,
            "reason": "exact duty cycle match required",
            "mismatches": mismatches,
        }

    if query_type == "polarity":
        for key in ("polarity_type", "ground_clamp_cable"):
            if key in proposed and key in ground_truth:
                if proposed[key] != ground_truth[key]:
                    mismatches.append(
                        f"{key}: proposed {proposed[key]}, expected {ground_truth[key]}"
                    )
        return {
            "valid": len(mismatches) == 0,
            "reason": "exact polarity match required",
            "mismatches": mismatches,
        }

    if query_type == "specifications":
        for key in proposed:
            if key in ground_truth and proposed[key] != ground_truth[key]:
                mismatches.append(
                    f"{key}: proposed {proposed[key]}, expected {ground_truth[key]}"
                )
        return {
            "valid": len(mismatches) == 0,
            "reason": "exact specification match required",
            "mismatches": mismatches,
        }

    # No validation rule for this query type — pass through
    return {"valid": True, "reason": "no deterministic validation rule", "mismatches": []}
