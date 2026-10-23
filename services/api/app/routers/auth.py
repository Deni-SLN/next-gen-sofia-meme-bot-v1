import os
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.core.config import settings
from app.core.security import create_access_token

router = APIRouter()


class LoginRequest(BaseModel):
    username: str | None = "admin"
    password: str


@router.post("/login")
def login(body: LoginRequest):
    input_user = (body.username or "").strip()
    input_pass = body.password.strip()

    is_valid = False
    actor_name = input_user if input_user else "admin"

    primary_u = (settings.primary_username or os.environ.get("SOFIA_PRIMARY_USERNAME") or "Deni26").strip()
    primary_p = (settings.primary_password or os.environ.get("SOFIA_PRIMARY_PASSWORD") or "Ronaldo07@").strip()

    if primary_u and primary_p:
        if input_user.lower() == primary_u.lower() and input_pass == primary_p:
            is_valid = True
            actor_name = primary_u
        elif input_pass == primary_p and input_user.lower() in ("", "admin"):
            is_valid = True
            actor_name = primary_u

    if not is_valid:
        fallback_p = (settings.admin_password or os.environ.get("SOFIA_ADMIN_PASSWORD") or "changeme").strip()
        if input_pass == fallback_p and input_user.lower() in ("admin", ""):
            is_valid = True
            actor_name = "admin"

    if not is_valid:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_PASSWORD", "message": "Username atau Password tidak sesuai"}},
        )
    token = create_access_token({"sub": actor_name, "actor": actor_name, "role": "admin"})
    return {"token": token, "actor": actor_name, "role": "admin"}
