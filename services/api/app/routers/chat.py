from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.db.session import get_db
from app.services import ai_chat

router = APIRouter(dependencies=[Depends(get_current_user)])


class CreateSessionRequest(BaseModel):
    title: Optional[str] = "Percakapan Baru"
    provider: Optional[str] = "openrouter"
    model: Optional[str] = "google/gemini-2.0-flash-exp:free"
    system_prompt: Optional[str] = None


class UpdateSessionRequest(BaseModel):
    title: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None


class ChatCompletionRequest(BaseModel):
    session_id: str
    message: str
    provider: Optional[str] = None
    model: Optional[str] = None
    api_key: Optional[str] = None
    system_prompt: Optional[str] = None


@router.get("/sessions")
def get_sessions(db: Session = Depends(get_db)):
    """List all user chat sessions."""
    sessions = ai_chat.list_chat_sessions(db)
    return {"sessions": sessions}


@router.post("/sessions", status_code=201)
def create_session(body: CreateSessionRequest, db: Session = Depends(get_db)):
    """Create a new chat session."""
    session = ai_chat.create_chat_session(
        db,
        title=body.title,
        provider=body.provider or "openrouter",
        model=body.model or "google/gemini-2.0-flash-exp:free",
        system_prompt=body.system_prompt,
    )
    return session


@router.get("/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)):
    """Get chat session and its full message history."""
    session = ai_chat.get_chat_session_with_messages(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return session


@router.put("/sessions/{session_id}")
def update_session(session_id: str, body: UpdateSessionRequest, db: Session = Depends(get_db)):
    """Update title, provider, or model of a chat session."""
    updated = ai_chat.update_chat_session(
        db,
        session_id,
        title=body.title,
        provider=body.provider,
        model=body.model,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return updated


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str, db: Session = Depends(get_db)):
    """Delete a chat session and all messages."""
    ok = ai_chat.delete_chat_session(db, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Chat session not found")
    return {"deleted": True, "session_id": session_id}


@router.get("/models")
def get_models(
    provider: str = Query("openrouter", description="openrouter, 9router, or google"),
    free_only: bool = Query(False, description="Filter only 100% free models"),
    refresh: bool = Query(False, description="Force refresh from live provider API"),
    api_key: Optional[str] = Query(None, description="Optional provider API key"),
):
    """Import and list available models with Free Tier detection."""
    models = ai_chat.fetch_available_models(
        provider=provider,
        api_key=api_key,
        free_only=free_only,
        force_refresh=refresh,
    )
    free_count = sum(1 for m in models if m.get("is_free"))
    return {
        "provider": provider,
        "total_models": len(models),
        "free_models_count": free_count,
        "free_only": free_only,
        "models": models,
    }


@router.get("/tools")
def get_tools():
    """List all available application tools that AI can read and call."""
    return {
        "tools_count": len(ai_chat.APPLICATION_TOOLS_SPEC),
        "tools": ai_chat.APPLICATION_TOOLS_SPEC,
    }


@router.post("/completions")
def post_completion(body: ChatCompletionRequest, db: Session = Depends(get_db)):
    """
    Send user message, execute tools if needed, save messages to DB, and return assistant response.
    """
    session = ai_chat.get_chat_session_with_messages(db, body.session_id)
    if not session:
        # Auto-create session if not found
        session = ai_chat.create_chat_session(
            db,
            title="Percakapan Baru",
            provider=body.provider or "openrouter",
            model=body.model or "google/gemini-2.0-flash-exp:free",
        )
        session["messages"] = []

    # 1. Save user message to database
    user_msg = ai_chat.save_chat_message(
        db,
        session_id=body.session_id,
        role="user",
        content=body.message,
    )

    # 2. Build conversation history
    history = session.get("messages", []) + [user_msg]

    provider = body.provider or session.get("provider") or "openrouter"
    model = body.model or session.get("model") or "google/gemini-2.0-flash-exp:free"

    # 3. Run completion with tools execution
    completion_res = ai_chat.run_chat_completion(
        messages=history,
        provider=provider,
        model=model,
        api_key=body.api_key,
        system_prompt=body.system_prompt or session.get("system_prompt"),
        db=db,
    )

    # 4. Save assistant response to database
    assistant_msg = ai_chat.save_chat_message(
        db,
        session_id=body.session_id,
        role="assistant",
        content=completion_res.get("content", ""),
        tool_calls=completion_res.get("tool_calls"),
        tool_results=completion_res.get("tool_results"),
        model=model,
    )

    return {
        "session_id": body.session_id,
        "user_message": user_msg,
        "assistant_message": assistant_msg,
        "model": model,
        "provider": provider,
    }
