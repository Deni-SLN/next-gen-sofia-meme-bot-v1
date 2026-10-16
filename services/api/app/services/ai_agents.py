from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.db.models import AIAgent
from app.providers.llm.schemas import validate


def list_agents(db: Session) -> list[AIAgent]:
    stmt = select(AIAgent).order_by(AIAgent.created_at.asc())
    return list(db.execute(stmt).scalars().all())


def create_agent(db: Session, data: dict) -> AIAgent:
    output_schema = data.get("output_schema") or {}
    if output_schema:
        # Validate schema structure using schemas.validate against dummy value
        validate({}, output_schema)
    agent = AIAgent(
        name=data["name"],
        description=data.get("description", ""),
        agent_type=data.get("agent_type", "analyst"),
        status=data.get("status", "active"),
        output_schema=output_schema,
        config=data.get("config") or {},
        created_at=datetime.now(timezone.utc),
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_agent(db: Session, agent_id: int) -> AIAgent | None:
    return db.execute(select(AIAgent).where(AIAgent.id == agent_id)).scalar_one_or_none()


def update_agent(db: Session, agent_id: int, data: dict) -> AIAgent:
    agent = get_agent(db, agent_id)
    if not agent:
        raise ValueError("AGENT_NOT_FOUND")
    for field in ("name", "description", "agent_type", "status", "output_schema", "config"):
        if field in data and data[field] is not None:
            setattr(agent, field, data[field])
    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, agent_id: int) -> bool:
    agent = get_agent(db, agent_id)
    if not agent:
        return False
    db.delete(agent)
    db.commit()
    return True
