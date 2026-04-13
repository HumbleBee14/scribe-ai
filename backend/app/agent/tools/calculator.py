"""Safe math expression evaluator using AST node whitelisting.

Parses expressions into an AST and only allows whitelisted operations.
No eval() used. Blocks all code injection attempts.

Supported: +, -, *, /, //, %, **, sqrt, abs, round, min, max,
           sin, cos, tan, log, log10, pow, ceil, floor, pi, e
"""
from __future__ import annotations

import ast
import math
import operator

_SAFE_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}

_SAFE_FUNCS = {
    "sqrt": math.sqrt,
    "abs": abs,
    "round": round,
    "min": min,
    "max": max,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "log": math.log,
    "log10": math.log10,
    "pow": math.pow,
    "ceil": math.ceil,
    "floor": math.floor,
}

_SAFE_CONSTANTS = {
    "pi": math.pi,
    "e": math.e,
}


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate an AST node. Only allows safe math operations."""
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.Name) and node.id in _SAFE_CONSTANTS:
        return _SAFE_CONSTANTS[node.id]
    if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_OPS:
        return _SAFE_OPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in _SAFE_FUNCS:
            args = [_eval_node(a) for a in node.args]
            return _SAFE_FUNCS[node.func.id](*args)
        raise ValueError(f"Unknown function: {ast.dump(node.func)}")
    raise ValueError(f"Unsupported expression: {ast.dump(node)}")


def safe_calculate(expression: str) -> dict:
    """Safely evaluate a math expression using AST parsing.

    Returns {"expression": str, "result": float} on success.
    Returns {"error": str} on failure.
    """
    try:
        tree = ast.parse(expression, mode="eval")
        result = _eval_node(tree)
        return {"expression": expression, "result": result}
    except (ValueError, TypeError, SyntaxError, ZeroDivisionError) as exc:
        return {"error": f"Calculation failed: {exc}"}
