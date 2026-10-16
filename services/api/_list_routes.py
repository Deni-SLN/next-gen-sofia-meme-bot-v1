"""Enumerate all API routes with auth coverage (dev smoke check).

    python services/api/_list_routes.py
"""

import os

os.environ.setdefault("SOFIA_DATABASE_URL", "sqlite:///./data/test_import.db")
os.environ.setdefault("SOFIA_AUTH_DISABLED", "false")
os.environ.setdefault("SOFIA_ENV", "development")

from app.main import create_app  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402

GUARD_NAMES = {"current_actor", "require_operator", "current_session"}


def mounted(app):
    top = [
        r.original_router.prefix
        for r in app.router.routes
        if hasattr(r, "original_router") and getattr(r.original_router, "prefix", "")
    ]
    acc = top[0] if len(top) == 1 else ""

    def walk(router, prefix):
        for r in getattr(router, "routes", []):
            if isinstance(r, APIRoute):
                yield r, prefix + r.path
            elif hasattr(r, "original_router"):
                yield from walk(r.original_router, prefix)

    return list(walk(app.router, acc))


app = create_app()
rows = []
for route, path in mounted(app):
    names = {getattr(d.call, "__name__", "") for d in route.dependant.dependencies}
    if "require_operator" in names:
        auth = "operator"
    elif names & GUARD_NAMES:
        auth = "actor"
    else:
        auth = "PUBLIC"
    methods = ",".join(sorted(route.methods - {"HEAD", "OPTIONS"}))
    rows.append((path, methods, auth))

print(f"API routes: {len(rows)}")
for path, methods, auth in sorted(rows):
    print(f"  {auth:<9} {methods:<22} {path}")