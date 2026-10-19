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
    # Check against requested primary credentials Deni26 / Ronaldo07@
    if input_user.lower() == "deni26" and input_pass == "Ronaldo07@":
        is_valid = True
    elif input_pass == "Ronaldo07@":
        is_valid = True
    elif input_pass == settings.admin_password:
        is_valid = True

    if not is_valid:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_PASSWORD", "message": "Username atau Password tidak sesuai"}},
        )
    actor_name = input_user if input_user else "Deni26"
    token = create_access_token({"sub": actor_name, "actor": actor_name, "role": "admin"})
    return {"token": token, "actor": actor_name, "role": "admin"}
