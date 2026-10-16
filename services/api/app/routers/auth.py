from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from app.core.config import settings
from app.core.security import create_access_token

router = APIRouter()


class LoginRequest(BaseModel):
    password: str


@router.post("/login")
def login(body: LoginRequest):
    if body.password != settings.admin_password:
        return JSONResponse(
            status_code=401,
            content={"error": {"code": "INVALID_PASSWORD", "message": "Invalid admin password"}},
        )
    token = create_access_token({"sub": "admin", "actor": "admin", "role": "admin"})
    return {"token": token, "actor": "admin", "role": "admin"}
