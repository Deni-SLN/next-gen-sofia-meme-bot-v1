"""Compare frontend API calls against the FastAPI route table.

Phase 5 exit gate: the UI must be wired to the real API. This catches drift
where a page calls an endpoint the backend does not serve.

SCOPE: paths only. A path can resolve while every field the UI reads from its
response is missing - which is exactly what happened on /performance/summary,
where six of nine rendered tiles had no backend field and this gate stayed
green. Field-level drift is covered by `services/api/tests/test_ui_contract.py`,
which parses the field lists the UI actually renders and asserts them against a
real response. Both run in CI.
"""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # tools/ -> repo root
sys.path.insert(0, str(ROOT / "services" / "api"))
os_env = None  # noqa: E305

# A path literal: starts at /api/v1, then consumes either an ordinary character
# (never a delimiter) or a complete `${...}` interpolation, which may itself
# contain a nested template such as `${q ? `?q=${q}` : ""}`. Stopping only at
# delimiters keeps each match inside a single literal.
_EXPR = r"\$\{(?:[^{}]|\{[^{}]*\})*\}"
PATH_RE = re.compile(r"/api/v1(?:[^`\"'?\s()${}]|" + _EXPR + r")*")


def _strip_query(s: str) -> str:
    """Cut at the first `?` that sits outside a `${...}` interpolation."""
    depth = 0
    for i, ch in enumerate(s):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "?" and depth == 0:
            return s[:i]
    return s


def _collapse_exprs(s: str) -> str:
    """Turn every `${...}` into `*`, innermost first (they may nest)."""
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\$\{[^{}]*\}", "*", s)
    return s


def _cut_query_ternary(s: str) -> str:
    """Drop a trailing `${cond ? "?a=b" : ""}` query builder.

    It sits at depth 0 and its body always contains `?`, whereas a real path
    segment interpolation (`/bot/${action}`) never does.
    """
    depth = 0
    i = 0
    while i < len(s):
        if s.startswith("${", i) and depth == 0:
            end = _match_brace(s, i + 1)
            if end != -1 and "?" in s[i : end + 1]:
                return s[:i]
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
        i += 1
    return s


def _match_brace(s: str, open_idx: int) -> int:
    """Index of the `}` closing the `{` at open_idx, or -1."""
    depth = 0
    for i in range(open_idx, len(s)):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def _clean(raw: str) -> str:
    """Normalise a captured literal into a comparable path pattern."""
    path = _cut_query_ternary(raw)
    path = _strip_query(path)
    path = _collapse_exprs(path)
    path = re.sub(r"/\*+", "/*", path)
    return path.rstrip("/") or path


def frontend_calls() -> set[str]:
    out: set[str] = set()
    for f in (ROOT / "apps" / "web" / "src").rglob("*"):
        if f.suffix not in (".ts", ".tsx") or not f.is_file():
            continue
        text = open(f, encoding="utf-8").read()
        for match in PATH_RE.finditer(text):
            cleaned = _clean(match.group(0))
            if cleaned:
                out.add(cleaned)
    return out


def backend_routes() -> set[str]:
    """Real paths from the OpenAPI schema.

    `app.routes` cannot be used here: FastAPI >=0.12x stores included routers as
    lazy `_IncludedRouter` objects that expose no `path`.
    """
    from app.main import create_app

    app = create_app()
    schema = app.openapi()
    paths = set()
    for raw in schema.get("paths") or {}:
        norm = re.sub(r"\{[^}]+\}", "*", raw)
        paths.add(norm)
        # also index the path without its final segment, so a UI call with a
        # literal id still resolves against a parametrised route
        parts = norm.split("/")
        for i in range(len(parts) - 1, 2, -1):
            paths.add("/".join(parts[:i]) + "/*")
    return paths


def _matches(pattern: str, routes: set[str]) -> bool:
    """A UI call matches if the path, or any prefix of it, is a real route."""
    segs = [s for s in pattern.split("/") if s]
    for i in range(1, len(segs) + 1):
        if "/" + "/".join(segs[:i]) in routes:
            return True
    return False


def main() -> int:
    calls = frontend_calls()
    routes = backend_routes()
    print(f"frontend endpoint patterns: {len(calls)}")
    print(f"backend /api/v1 routes:      {len(routes)}")

    missing = [c for c in sorted(calls) if not _matches(c, routes)]

    if missing:
        print(f"\nMISSING on backend ({len(missing)}):")
        for m in missing:
            print("  ", m)
        return 1
    print("\nOK: every frontend endpoint resolves to a backend route.")
    print("     (paths only - field drift is covered by services/api/tests/test_ui_contract.py)")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())