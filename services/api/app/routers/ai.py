from datetime import datetime
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.core.security import get_current_user
from app.db.session import get_db
from app.services import ai_agents

router = APIRouter(dependencies=[Depends(get_current_user)])


def _row_to_dict(obj) -> dict:
    d = {c.name: getattr(obj, c.name) for c in obj.__table__.columns}
    for k, v in d.items():
        if isinstance(v, datetime):
            d[k] = v.isoformat() if v else None
    return d


class AgentCreateRequest(BaseModel):
    name: str
    description: str = ""
    agent_type: str = "analyst"
    output_schema: dict = {}
    config: dict = {}


class AgentUpdateRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    agent_type: str | None = None
    status: str | None = None
    output_schema: dict | None = None
    config: dict | None = None


@router.get("/agents")
def get_agents(db: Session = Depends(get_db)):
    agents = ai_agents.list_agents(db)
    return {"agents": [_row_to_dict(a) for a in agents]}


@router.post("/agents", status_code=201)
def create_agent(body: AgentCreateRequest, db: Session = Depends(get_db)):
    agent = ai_agents.create_agent(db, body.model_dump())
    return _row_to_dict(agent)


@router.get("/agents/{agent_id}")
def get_agent(agent_id: int, db: Session = Depends(get_db)):
    agent = ai_agents.get_agent(db, agent_id)
    if not agent:
        return JSONResponse(status_code=404, content={"error": {"code": "AGENT_NOT_FOUND", "message": "Agent not found"}})
    return _row_to_dict(agent)


@router.put("/agents/{agent_id}")
def update_agent(agent_id: int, body: AgentUpdateRequest, db: Session = Depends(get_db)):
    try:
        agent = ai_agents.update_agent(db, agent_id, body.model_dump(exclude_unset=True))
        return _row_to_dict(agent)
    except ValueError as e:
        return JSONResponse(status_code=404, content={"error": {"code": str(e), "message": "Agent not found"}})


@router.delete("/agents/{agent_id}")
def delete_agent(agent_id: int, db: Session = Depends(get_db)):
    ok = ai_agents.delete_agent(db, agent_id)
    if not ok:
        return JSONResponse(status_code=404, content={"error": {"code": "AGENT_NOT_FOUND", "message": "Agent not found"}})
    return {"deleted": True}
