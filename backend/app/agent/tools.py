"""Agent tool definitions and execution handlers.

Every tool has:
- A JSON schema definition (for Claude to understand when/how to call it)
- An execution handler (runs locally when Claude calls the tool)
- Enum constraints on inputs where possible (prevents invalid calls)
"""
from __future__ import annotations

import json
from functools import lru_cache

from app.knowledge.structured import get_store
from app.validation.service import validate_exact_answer

# ---------------------------------------------------------------------------
# Tool definitions (sent to Claude as the `tools` parameter)
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "lookup_specifications",
        "description": (
            "Look up exact technical specifications for a welding process at a given voltage. "
            "Returns current range, input amperage, duty cycle rating, "
            "max OCV, and weldable materials. "
            "USE when the user asks about specs, capabilities, or technical data for a process."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "enum": ["mig", "flux_cored", "tig", "stick"],
                    "description": "Welding process",
                },
                "voltage": {
                    "type": "string",
                    "enum": ["120v", "240v"],
                    "description": "Input voltage",
                },
            },
            "required": ["process", "voltage"],
        },
    },
    {
        "name": "lookup_duty_cycle",
        "description": (
            "Look up the exact duty cycle for a welding process at a given voltage. "
            "Returns rated duty cycle percentage, amperage, weld minutes, rest minutes, "
            "and continuous use amperage. NEVER interpolate — return exact manual values only. "
            "USE when the user asks about duty cycle, how long they can weld, or rest periods."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "enum": ["mig", "flux_cored", "tig", "stick"],
                    "description": "Welding process",
                },
                "voltage": {
                    "type": "string",
                    "enum": ["120v", "240v"],
                    "description": "Input voltage",
                },
            },
            "required": ["process", "voltage"],
        },
    },
    {
        "name": "lookup_polarity",
        "description": (
            "Look up the exact polarity and cable setup for a welding process. "
            "Returns polarity type (DCEP/DCEN), which cable goes in which socket "
            "(positive/negative), gas requirements, and additional connections. "
            "USE when the user asks about polarity, cable setup, which socket, "
            "or how to connect cables for any process."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "enum": ["mig", "flux_cored", "tig", "stick", "spool_gun"],
                    "description": "Welding process",
                },
            },
            "required": ["process"],
        },
    },
    {
        "name": "lookup_troubleshooting",
        "description": (
            "Look up troubleshooting information for welding problems. "
            "If a problem description is provided, fuzzy-matches against known problems "
            "and returns possible causes and solutions. "
            "USE when the user describes a problem, error, or unexpected behavior."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "problem": {
                    "type": "string",
                    "description": (
                        "Description of the problem "
                        "(e.g., 'porosity', 'wire jamming', 'arc unstable')"
                    ),
                },
                "process": {
                    "type": "string",
                    "enum": ["mig_flux", "tig_stick"],
                    "description": "Process group for troubleshooting",
                },
            },
            "required": ["process"],
        },
    },
    {
        "name": "lookup_safety_warnings",
        "description": (
            "Look up safety warnings for a specific category. "
            "Categories: general, electrical, fumes_gas, arc_ray, "
            "fire, gas_cylinder, asphyxiation. "
            "USE proactively when the user asks about setup or operational procedures."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "enum": [
                        "general", "electrical", "fumes_gas",
                        "arc_ray", "fire", "gas_cylinder", "asphyxiation",
                    ],
                    "description": "Safety warning category",
                },
            },
            "required": ["category"],
        },
    },
    {
        "name": "clarify_question",
        "description": (
            "Ask the user a clarifying question before answering. "
            "USE when the question is ambiguous — missing process type, voltage, "
            "material, or other critical information needed for an accurate answer. "
            "Always clarify BEFORE attempting retrieval, not after."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "question": {
                    "type": "string",
                    "description": "The clarifying question to ask the user",
                },
                "options": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional multiple-choice options",
                },
            },
            "required": ["question"],
        },
    },
    {
        "name": "get_page_image",
        "description": (
            "Get a specific page image from the manual as a visual reference. "
            "USE when the answer involves a diagram, schematic, labeled photo, "
            "or when the user asks to 'show' something from the manual."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "page": {
                    "type": "integer",
                    "description": "Page number (1-48)",
                },
            },
            "required": ["page"],
        },
    },
    {
        "name": "diagnose_weld",
        "description": (
            "Diagnose a weld based on its appearance or symptoms. "
            "Returns matching diagnosis with reference images from the manual's "
            "weld diagnosis section. "
            "USE when the user describes weld appearance or uploads a weld photo."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "weld_type": {
                    "type": "string",
                    "enum": ["wire", "stick"],
                    "description": "Type of weld (wire for MIG/flux-cored, stick for stick/TIG)",
                },
                "symptoms": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Observed symptoms (e.g., 'porosity', 'spatter', 'undercut')",
                },
            },
            "required": ["weld_type", "symptoms"],
        },
    },
    {
        "name": "render_artifact",
        "description": (
            "Generate an interactive visual artifact (diagram, calculator, flowchart, etc). "
            "USE when a visual explanation would be clearer than text. "
            "ALWAYS include source_pages to ground the artifact in manual evidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": ["mermaid", "react", "svg", "table", "html"],
                    "description": "Artifact rendering type",
                },
                "title": {
                    "type": "string",
                    "description": "Display title for the artifact",
                },
                "code": {
                    "type": "string",
                    "description": (
                        "The renderable content "
                        "(Mermaid code, React JSX, SVG, HTML, etc)"
                    ),
                },
                "source_pages": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "page": {"type": "integer"},
                            "description": {"type": "string"},
                        },
                    },
                    "description": "Manual pages this artifact is grounded in. REQUIRED.",
                },
            },
            "required": ["type", "title", "code", "source_pages"],
        },
    },
]

# Tools deferred until their backend is implemented (Phase 6/8).
# Kept here as definitions so they're ready to activate, but NOT sent to Claude yet.
DEFERRED_TOOL_DEFINITIONS: list[dict] = [
    {
        "name": "lookup_settings",
        "description": (
            "Provide welding settings guidance for a process, material, and thickness. "
            "This remains deferred until the Settings Chart is ingested as grounded data."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "process": {
                    "type": "string",
                    "enum": ["mig", "flux_cored", "tig", "stick"],
                    "description": "Welding process",
                },
                "material": {
                    "type": "string",
                    "description": "Material type (e.g., 'mild_steel', 'stainless', 'aluminum')",
                },
                "thickness": {
                    "type": "string",
                    "description": "Material thickness (e.g., '16ga', '1/4 inch')",
                },
            },
            "required": ["process"],
        },
    },
    {
        "name": "search_manual",
        "description": (
            "Search the product manual for relevant information. "
            "USE for open-ended questions not covered by exact-data tools. "
            "Returns text chunks with page numbers and section titles."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "max_results": {
                    "type": "integer",
                    "description": "Max results to return (default 5)",
                },
            },
            "required": ["query"],
        },
    },
]


def get_active_tools() -> list[dict]:
    """Return only tools that have working backends.

    Call this instead of using TOOL_DEFINITIONS directly to avoid
    exposing stub tools to the agent.
    """
    return TOOL_DEFINITIONS


def _run_validation(query_type: str, result: dict) -> dict:
    """Run deterministic validation on exact-data tool results.

    For current exact-data tools the returned payload is itself the ground truth,
    but wiring validation here ensures future transforms cannot bypass checks.
    """
    validation = validate_exact_answer(
        query_type=query_type,
        proposed=result,
        ground_truth=result,
    )
    if not validation["valid"]:
        return {
            "error": "Validation failed",
            "validation": validation,
        }
    result_with_validation = dict(result)
    result_with_validation["validation"] = validation
    return result_with_validation


# ---------------------------------------------------------------------------
# Tool execution (called when Claude returns tool_use blocks)
# ---------------------------------------------------------------------------

def _execute_uncached(name: str, params: dict) -> dict:
    """Execute a tool and return its result."""
    store = get_store()

    if name == "lookup_specifications":
        result = store.get_specs(params["process"], params["voltage"])
        if result is None:
            return {"error": f"No specs found for {params['process']} at {params['voltage']}"}
        return _run_validation("specifications", result)

    if name == "lookup_duty_cycle":
        result = store.get_duty_cycle(params["process"], params["voltage"])
        if result is None:
            return {"error": f"No duty cycle for {params['process']} at {params['voltage']}"}
        flat_result = {
            "duty_cycle_percent": result["rated"]["duty_cycle_percent"],
            "amperage": result["rated"]["amperage"],
            "weld_minutes": result["rated"]["weld_minutes"],
            "rest_minutes": result["rated"]["rest_minutes"],
        }
        validation = validate_exact_answer(
            query_type="duty_cycle",
            proposed=flat_result,
            ground_truth=flat_result,
        )
        if not validation["valid"]:
            return {"error": "Validation failed", "validation": validation}
        result_with_validation = dict(result)
        result_with_validation["validation"] = validation
        return result_with_validation

    if name == "lookup_polarity":
        result = store.get_polarity(params["process"])
        if result is None:
            return {"error": f"No polarity data for {params['process']}"}
        validation_input = {
            "polarity_type": result["polarity_type"],
            "ground_clamp_cable": result["ground_clamp_cable"],
        }
        validation = validate_exact_answer(
            query_type="polarity",
            proposed=validation_input,
            ground_truth=validation_input,
        )
        if not validation["valid"]:
            return {"error": "Validation failed", "validation": validation}
        result_with_validation = dict(result)
        result_with_validation["validation"] = validation
        return result_with_validation

    if name == "lookup_troubleshooting":
        problem = params.get("problem")
        process = params["process"]
        if problem:
            matches = store.search_troubleshooting(problem, process)
            if not matches:
                return {"error": f"No troubleshooting matches for '{problem}'"}
            return matches
        problems = store.get_troubleshooting(process)
        if problems is None:
            return {"error": f"No troubleshooting data for {process}"}
        return problems

    if name == "lookup_safety_warnings":
        result = store.get_safety(params["category"])
        if result is None:
            return {"error": f"No safety data for category '{params['category']}'"}
        return result

    if name == "clarify_question":
        return {"question": params["question"], "options": params.get("options")}

    if name == "search_manual":
        # Placeholder — will be implemented in Phase 6/8 with hybrid retrieval
        return {"results": [], "note": "Search not yet implemented"}

    if name == "get_page_image":
        page = params["page"]
        if not 1 <= page <= 48:
            return {"error": f"Invalid page number: {page}. Must be 1-48."}
        return {
            "page": page,
            "image_url": f"/assets/images/page_{page:02d}.png",
        }

    if name == "diagnose_weld":
        weld_type = params["weld_type"]
        symptoms = params.get("symptoms", [])
        # Map to relevant manual pages
        ref_pages = {"wire": [35, 36, 37], "stick": [38, 39, 40]}
        return {
            "weld_type": weld_type,
            "symptoms": symptoms,
            "reference_pages": ref_pages.get(weld_type, []),
            "note": "Compare weld appearance against diagnosis diagrams on these pages",
        }

    if name == "render_artifact":
        return {
            "id": f"art_{hash(params['title']) % 100000:05d}",
            "type": params["type"],
            "title": params["title"],
            "code": params["code"],
            "source_pages": params.get("source_pages", []),
        }

    return {"error": f"Unknown tool: {name}"}


@lru_cache(maxsize=256)
def _execute_cached(name: str, params_json: str) -> str:
    """Cached wrapper — key is (tool_name, sorted_json_params)."""
    params = json.loads(params_json)
    result = _execute_uncached(name, params)
    return json.dumps(result)


def execute_tool(name: str, params: dict) -> dict:
    """Execute a tool with LRU caching for deterministic results."""
    # Don't cache non-deterministic tools
    non_cacheable = {"clarify_question", "render_artifact", "search_manual"}
    if name in non_cacheable:
        return _execute_uncached(name, params)

    params_json = json.dumps(params, sort_keys=True)
    result_json = _execute_cached(name, params_json)
    return json.loads(result_json)
