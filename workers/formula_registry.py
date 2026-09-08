"""
workers.formula_registry — callable Python registry for all 119 vault formulas.

Architecture (Option D from /talk)
───────────────────────────────────
  Notion (documentation) → sync_notion patches formula_dictionary.yaml
  formula_dictionary.yaml (canonical)  → FormulaRegistry loads at startup
  FormulaRegistry.call("F_CAIRRN_COMPOSITE", z=0.8, x=0.5, …) → float
  MCP tools: formula_call, formula_inspect

FormulaSpec
───────────
Each formula entry carries:
  id          — unique key (F_CONSTRAINT_VAR, …)
  label       — human name
  latex       — original math expression from the YAML `expr` field
  python_expr — Python expression string (auto-translated or manual override)
  variables   — symbol → semantic field name mapping
  output      — name of the computed output variable
  layer       — CAIRRN layer (1, 2, 3, X, Z)
  status      — "ready" | "unimplemented"
  note        — why unimplemented, or empty

Auto-translation
────────────────
The YAML `expr` field is already close to Python for most formulas.
The translator applies these transforms in order:

  1. Strip `<output> = ` prefix  →  extract RHS
  2. |…|  →  abs(…)  (inner-first, iterative regex)
  3. ^     →  **
  4. Trailing comments (`where …`, `if … else …`) are stripped or handled
  5. Conditional single-line → ternary
  6. Functions (sqrt, exp, tanh, log2, …) stay; they live in the eval namespace

Formulas that contain derivative notation (d/…, ∇, ∂), iterative update rules
(x_{n+1} =), infinite sums, or non-evaluable constructs are marked
status="unimplemented". Their `python_expr` field is empty; calling them
raises FormulaNotReady.

Extending
─────────
Add a `python_expr` key to any entry in formula_dictionary.yaml to override
the auto-translator:

    - id: F_CUSTOM
      expr: "some latex notation"
      python_expr: "abs(a) * math.exp(-b * t)"
      ...

The explicit `python_expr` is always used over the auto-translated one.

Math namespace
──────────────
All expressions are eval'd in a namespace that includes:
  abs, sqrt, exp, log, log2, tanh, sinh, cosh, floor, ceil, round,
  pi, e (Euler), inf,
  sigmoid(x) = 1 / (1 + exp(-x)),
  clamp(v, lo, hi) = max(lo, min(hi, v)),
  sign(x),
  dot(a, b)  — sum of element-wise products (for list/tuple args),
  norm(a)    — Euclidean norm.

Plus: all keyword arguments passed to .call() by the caller.

Usage
─────
  from workers.formula_registry import REGISTRY

  result = REGISTRY.call("F_CAIRRN_COMPOSITE", z=0.8, x=0.5, c=0.3, y=0.9, Ti=0.1)
  info   = REGISTRY.inspect("F_CAIRRN_COMPOSITE")
  all_f  = REGISTRY.inspect()               # list of all specs

  REGISTRY.reload()                          # hot-reload YAML without restart
"""
from __future__ import annotations

import math
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

_YAML_PATH      = Path(__file__).parent.parent / "config" / "formulas" / "formula_dictionary.yaml"
_OVERRIDES_PATH = Path(__file__).parent.parent / "config" / "formulas" / "python_overrides.yaml"

# ---------------------------------------------------------------------------
# Math eval namespace
# ---------------------------------------------------------------------------

def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-float(x)))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, float(v)))


def _sign(x: float) -> float:
    return 0.0 if x == 0 else (1.0 if x > 0 else -1.0)


def _dot(a: Any, b: Any) -> float:
    return float(sum(ai * bi for ai, bi in zip(a, b)))


def _norm(a: Any) -> float:
    return math.sqrt(sum(x * x for x in a))


_MATH_NS: dict[str, Any] = {
    # builtins
    "__builtins__": {},
    "abs":    abs,
    "round":  round,
    "max":    max,
    "min":    min,
    "sum":    sum,
    "len":    len,
    "range":  range,
    "set":    set,
    "list":   list,
    "tuple":  tuple,
    "zip":    zip,
    # math module
    "sqrt":   math.sqrt,
    "exp":    math.exp,
    "log":    math.log,
    "log2":   math.log2,
    "log10":  math.log10,
    "tanh":   math.tanh,
    "sinh":   math.sinh,
    "cosh":   math.cosh,
    "floor":  math.floor,
    "ceil":   math.ceil,
    "pi":     math.pi,
    "e":      math.e,
    "inf":    math.inf,
    "nan":    math.nan,
    # domain helpers
    "sigmoid": _sigmoid,
    "sigma":   _sigmoid,    # alias used in formulas
    "clamp":   _clamp,
    "sign":    _sign,
    "dot":     _dot,
    "norm":    _norm,
}


# ---------------------------------------------------------------------------
# Auto-translator:  math expr string  →  Python expression string
# ---------------------------------------------------------------------------

# Patterns that indicate the formula is not a simple point-evaluation
_UNIMPLEMENTABLE = re.compile(
    r"d/d[a-zA-Z]|∇|∂|\{n\+1\}|x_\{|_{n\+|_{i[-−]|i=1\.\.|j in |"
    r"for [a-z]+ in |grad_|step|update|iterate|converge|∞|infinity",
    re.IGNORECASE,
)


def _strip_rhs(expr: str) -> str:
    """Remove `output =` prefix, keeping only the RHS."""
    # Match patterns: "x_c = ...", "SCUP = ...", "V(x) = ...", "neg_exp(x) = ..."
    m = re.match(r"^[A-Za-z_()^/*+\[\]0-9,\s]+?=\s*", expr)
    if m:
        rhs = expr[m.end():].strip()
        # Only strip if RHS is not empty and doesn't look like it starts another =
        if rhs and not rhs.startswith("="):
            return rhs
    return expr


def _abs_transform(expr: str) -> str:
    """Replace |inner| with abs(inner), innermost first."""
    prev = None
    while prev != expr:
        prev = expr
        expr = re.sub(r'\|([^|]+)\|', r'abs(\1)', expr)
    return expr


def _caret_to_pow(expr: str) -> str:
    """Replace ^ with **."""
    return expr.replace("^", "**")


_UNICODE_MAP: list[tuple[str, str]] = [
    # Math operators
    ("\u2212", "-"),    # − MINUS SIGN → hyphen-minus
    ("\u00b7", "*"),    # · MIDDLE DOT → asterisk
    ("\u00d7", "*"),    # × MULTIPLICATION SIGN
    ("\u00f7", "/"),    # ÷ DIVISION SIGN
    ("\u2264", "<="),   # ≤
    ("\u2265", ">="),   # ≥
    ("\u2260", "!="),   # ≠
    ("\u2228", " or "), # ∨ LOGICAL OR
    ("\u2227", " and "),# ∧ LOGICAL AND
    ("\u221a", "sqrt"), # √
    ("\u03a3", "sum"),  # Σ SIGMA (summation)
    # Greek letters used as variable names
    ("\u03c4", "tau"),
    ("\u03bb", "lam"),
    ("\u03b7", "eta"),
    ("\u03ba", "kappa"),
    ("\u03b1", "alpha"),
    ("\u03b2", "beta"),
    ("\u03c8", "Psi"),
    ("\u03c6", "phi"),
    ("\u03b5", "eps"),
    ("\u03b4", "delta"),
    ("\u03bc", "mu"),
    ("\u03c9", "omega"),
    ("\u03b3", "gamma"),
    # Superscripts / special
    ("\u00b2", "**2"),  # ²
    ("\u00b3", "**3"),  # ³
    ("\u221e", "inf"),  # ∞
]


def _normalize_unicode(expr: str) -> str:
    """Replace Unicode math/Greek characters with ASCII Python equivalents."""
    for uni, asc in _UNICODE_MAP:
        expr = expr.replace(uni, asc)
    # Replace Python keyword `lambda` used as a variable name with `lam`
    expr = re.sub(r'\blambda\b', 'lam', expr)
    return expr


def _strip_trailing_comments(expr: str) -> str:
    """Remove trailing `where …` annotation text only — never strip math parens."""
    # "Tws = Tn / K   where Tn >= Tip"  → "Tn / K"
    expr = re.sub(r'\s{2,}where\s+.*$', '', expr, flags=re.IGNORECASE)
    return expr.strip()


def _simple_ternary(expr: str) -> Optional[str]:
    """
    Convert "val  if condition  else other_val" into Python ternary.
    Also handles "1 if A and B else 0" patterns from indicator formulas.
    Returns None if not applicable.
    """
    m = re.match(
        r'^(.+?)\s+if\s+(.+?)\s+else\s+(.+)$',
        expr.strip(),
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        val, cond, other = m.group(1).strip(), m.group(2).strip(), m.group(3).strip()
        return f"({val}) if ({cond}) else ({other})"
    return None


def _translate(expr_raw: str, python_override: Optional[str] = None) -> tuple[str, str]:
    """
    Translate a formula `expr` string to a Python expression.

    Returns (python_expr, status) where status is "ready" or "unimplemented".
    """
    if python_override:
        return python_override.strip(), "ready"

    if not expr_raw:
        return "", "unimplemented"

    expr = expr_raw.strip()

    # Hard gate: contains calculus / iterative notation
    if _UNIMPLEMENTABLE.search(expr):
        return "", "unimplemented"

    expr = _normalize_unicode(expr)
    expr = _strip_trailing_comments(expr)
    expr = _strip_rhs(expr)
    expr = _abs_transform(expr)
    expr = _caret_to_pow(expr)

    # Conditional → ternary
    ternary = _simple_ternary(expr)
    if ternary:
        expr = ternary

    # Validate by compiling
    try:
        compile(expr, "<formula>", "eval")
        return expr, "ready"
    except SyntaxError:
        return expr, "unimplemented"


# ---------------------------------------------------------------------------
# FormulaSpec
# ---------------------------------------------------------------------------

@dataclass
class FormulaSpec:
    """Compiled descriptor for one formula."""
    id:          str
    label:       str
    latex:       str                    # original math string from YAML
    python_expr: str                    # Python-evaluable expression
    variables:   dict[str, str]         # symbol → semantic field name
    output:      str                    # name of the result variable
    layer:       str                    # CAIRRN layer (1/2/3/X/Z)
    status:      str                    # "ready" | "unimplemented"
    note:        str = ""               # why unimplemented
    source:      str = ""
    _callable:   Any = field(default=None, repr=False, compare=False)

    def to_dict(self) -> dict:
        return {
            "id":          self.id,
            "label":       self.label,
            "latex":       self.latex,
            "python_expr": self.python_expr,
            "variables":   self.variables,
            "output":      self.output,
            "layer":       self.layer,
            "status":      self.status,
            "note":        self.note,
            "source":      self.source,
        }


# ---------------------------------------------------------------------------
# FormulaNotReady
# ---------------------------------------------------------------------------

class FormulaNotReady(Exception):
    """Raised when calling a formula that has status='unimplemented'."""


class FormulaNotFound(KeyError):
    """Raised when a formula_id is not in the registry."""


# ---------------------------------------------------------------------------
# FormulaRegistry
# ---------------------------------------------------------------------------

class FormulaRegistry:
    """
    Central callable registry for all vault formulas.

    Load once at module import via the singleton REGISTRY, or create a custom
    instance from a different YAML path in tests.
    """

    def __init__(self, yaml_path: Path = _YAML_PATH) -> None:
        self._yaml_path = yaml_path
        self._specs:    dict[str, FormulaSpec] = {}
        self._load()

    # ── loading ───────────────────────────────────────────────────────────

    def _load(self) -> None:
        try:
            import yaml  # type: ignore[import]
        except ImportError:
            print(
                "[formula_registry] PyYAML not installed — registry empty",
                file=sys.stderr,
            )
            return

        if not self._yaml_path.exists():
            print(
                f"[formula_registry] YAML not found: {self._yaml_path}",
                file=sys.stderr,
            )
            return

        with open(self._yaml_path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        # Load python_expr overrides from the companion overrides file.
        overrides: dict[str, str] = {}
        if _OVERRIDES_PATH.exists():
            with open(_OVERRIDES_PATH, encoding="utf-8") as fh:
                raw_overrides = yaml.safe_load(fh) or {}
            overrides = {
                k: v.strip()
                for k, v in raw_overrides.items()
                if isinstance(v, str) and v.strip()
            }

        raw_formulas: list[dict] = data.get("formulas", [])
        specs: dict[str, FormulaSpec] = {}

        for raw in raw_formulas:
            fid = raw.get("id", "")
            if not fid:
                continue

            latex   = raw.get("expr", "")
            # Override priority: inline YAML > overrides file > auto-translate
            override = raw.get("python_expr") or overrides.get(fid)
            py_expr, status = _translate(latex, override)

            variables = raw.get("variables") or raw.get("vars") or {}
            if isinstance(variables, str):
                variables = {}

            note = ""
            if status == "unimplemented":
                note = (
                    raw.get("note")
                    or "Contains iterative/calculus notation — add 'python_expr' override in YAML"
                )

            spec = FormulaSpec(
                id          = fid,
                label       = raw.get("label", fid),
                latex       = latex,
                python_expr = py_expr,
                variables   = dict(variables),
                output      = raw.get("output", ""),
                layer       = str(raw.get("layer", "")),
                status      = status,
                note        = note,
                source      = raw.get("source", ""),
            )
            specs[fid] = spec

        self._specs = specs
        n_ready = sum(1 for s in specs.values() if s.status == "ready")
        print(
            f"[formula_registry] loaded {len(specs)} formulas"
            f" ({n_ready} ready, {len(specs) - n_ready} unimplemented)",
            file=sys.stderr,
        )

    def reload(self) -> None:
        """Hot-reload YAML without restarting the process."""
        self._load()

    # ── call ──────────────────────────────────────────────────────────────

    def call(self, formula_id: str, **kwargs: Any) -> float:
        """
        Evaluate a formula with the supplied variable bindings.

        Parameters
        ----------
        formula_id   Exact formula id string (e.g. "F_CAIRRN_COMPOSITE").
        **kwargs     Variable bindings matching the formula's `variables` map.
                     Extra kwargs are silently available in the expression scope.

        Returns
        -------
        float        The evaluated result.

        Raises
        ------
        FormulaNotFound   Unknown formula_id.
        FormulaNotReady   Formula has status="unimplemented".
        ValueError         Evaluation produced a non-numeric result.
        """
        spec = self._get(formula_id)
        if spec.status != "ready":
            raise FormulaNotReady(
                f"Formula '{formula_id}' is not yet implemented as Python. "
                f"Add a 'python_expr' key to its YAML entry. Note: {spec.note}"
            )

        ns = dict(_MATH_NS)
        ns.update(kwargs)

        try:
            result = eval(spec.python_expr, ns)  # noqa: S307
        except Exception as exc:
            raise ValueError(
                f"Error evaluating '{formula_id}' with expr={spec.python_expr!r}: {exc}"
            ) from exc

        try:
            return float(result)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"Formula '{formula_id}' returned non-numeric value: {result!r}"
            ) from exc

    # ── inspect ───────────────────────────────────────────────────────────

    def inspect(self, formula_id: str = "") -> dict | list[dict]:
        """
        Return spec info for one formula or a summary list of all formulas.

        Parameters
        ----------
        formula_id   If non-empty, return the full spec dict for that formula.
                     If empty, return a list of compact dicts for all formulas.
        """
        if formula_id:
            return self._get(formula_id).to_dict()

        return [
            {
                "id":          s.id,
                "label":       s.label,
                "status":      s.status,
                "layer":       s.layer,
                "variables":   list(s.variables.keys()),
                "output":      s.output,
            }
            for s in self._specs.values()
        ]

    def ready_ids(self) -> list[str]:
        """Return ids of all formulas with status='ready'."""
        return [fid for fid, s in self._specs.items() if s.status == "ready"]

    def unimplemented_ids(self) -> list[str]:
        """Return ids of all formulas with status='unimplemented'."""
        return [fid for fid, s in self._specs.items() if s.status != "ready"]

    def patch_from_notion(self, formula_id: str, latex: str) -> bool:
        """
        Update a formula's latex string from a Notion equation block.

        Called by sync_notion after pulling new equation blocks.
        Does NOT overwrite python_expr — the operator must add that manually
        or re-run the YAML sync and reload.

        Returns True if the spec was found and updated.
        """
        if formula_id not in self._specs:
            return False
        spec = self._specs[formula_id]
        if spec.latex == latex:
            return False
        # Rebuild spec with new latex.  Only preserve an explicit python_expr
        # override if the formula still cannot be auto-translated from the new latex.
        new_py, new_status = _translate(latex)
        if new_status == "unimplemented" and spec.python_expr:
            new_py, new_status = spec.python_expr, "ready"
        py_expr, status = new_py, new_status
        self._specs[formula_id] = FormulaSpec(
            id          = spec.id,
            label       = spec.label,
            latex       = latex,
            python_expr = py_expr,
            variables   = spec.variables,
            output      = spec.output,
            layer       = spec.layer,
            status      = status,
            note        = spec.note,
            source      = "notion",
        )
        return True

    # ── private ───────────────────────────────────────────────────────────

    def _get(self, formula_id: str) -> FormulaSpec:
        try:
            return self._specs[formula_id]
        except KeyError as exc:
            available = sorted(self._specs)[:10]
            raise FormulaNotFound(
                f"Formula '{formula_id}' not found. "
                f"First 10 ids: {available}"
            ) from exc

    def __len__(self) -> int:
        return len(self._specs)

    def __contains__(self, formula_id: str) -> bool:
        return formula_id in self._specs

    def assert_ready(self, *formula_ids: str) -> None:
        """
        Assert that all listed formula IDs are present and ready.

        Raises FormulaNotReady listing every missing / unimplemented formula.
        Use this at function or class level to make formula dependencies
        explicit and fail-fast rather than silently wrong.
        """
        missing: list[str] = []
        for fid in formula_ids:
            if fid not in self._specs:
                missing.append(f"{fid} (not found)")
                continue
            spec = self._specs[fid]
            if spec.status != "ready":
                missing.append(f"{fid} ({spec.status})")
        if missing:
            raise FormulaNotReady(
                "Required formulas are not ready: " + ", ".join(missing)
            )


# ---------------------------------------------------------------------------
# @requires_formulas decorator
# ---------------------------------------------------------------------------

def requires_formulas(*formula_ids: str):
    """
    Decorator that enforces formula availability before a function runs.

    Usage
    -----
    @requires_formulas("F_COSINE_SIMILARITY", "F_JACCARD_AFFINITY")
    def my_scoring_fn(...):
        ...

    Raises FormulaNotReady at call time (not import time) if any listed
    formula is absent or unimplemented.  This makes the Python contract
    explicit: decorated functions cannot run without their math.
    """
    import functools

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            REGISTRY.assert_ready(*formula_ids)
            return fn(*args, **kwargs)
        # Attach metadata so introspection tools can surface dependencies
        wrapper._required_formulas = tuple(formula_ids)
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

REGISTRY = FormulaRegistry()
