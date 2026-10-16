"""Watchlist endpoints (FR §12.3)."""

from app.api.v1.deps import current_actor, require_operator
from app.core.errors import ConflictError, NotFoundError, ValidationError
from app.db.session import get_db
from app.models.market import Token
from app.models.system import Watchlist, WatchlistItem
from app.services.audit_service import write_audit
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter(prefix="/watchlists", tags=["watchlist"])


def _watch_json(w: Watchlist) -> dict:
    return {"id": w.id, "name": w.name, "description": w.description, "created_at": w.created_at.isoformat() if w.created_at else None}


@router.get("")
def list_watchlists(db: Session = Depends(get_db), actor: str = Depends(current_actor)):
    rows = db.query(Watchlist).order_by(Watchlist.created_at.desc()).all()
    out = []
    for w in rows:
        items = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id == w.id).all()
        d = _watch_json(w)
        d["items"] = [
            {"mint_address": i.mint_address, "token_id": i.token_id, "note": i.note} for i in items
        ]
        out.append(d)
    return {"items": out}


@router.post("")
def create_watchlist(payload: dict, db: Session = Depends(get_db), actor: str = Depends(require_operator)):
    name = (payload or {}).get("name", "").strip()
    if not name:
        raise ValidationError("name required")
    if db.query(Watchlist).filter(Watchlist.name == name).first():
        raise ConflictError("watchlist name already exists")
    w = Watchlist(name=name, description=(payload or {}).get("description"))
    db.add(w)
    db.commit()
    write_audit(actor, "create_watchlist", "watchlist", w.id, {"name": name}, db)
    return _watch_json(w)


@router.post("/{watchlist_id}/items")
def add_item(
    watchlist_id: str,
    payload: dict,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    w = db.get(Watchlist, watchlist_id)
    if w is None:
        raise NotFoundError("watchlist", watchlist_id)
    mint = (payload or {}).get("mint_address", "").strip()
    if not mint:
        raise ValidationError("mint_address required")
    if db.query(WatchlistItem).filter(
        WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.mint_address == mint
    ).first():
        raise ConflictError("token already in watchlist")
    token = db.query(Token).filter(Token.mint_address == mint).first()
    item = WatchlistItem(
        watchlist_id=watchlist_id, mint_address=mint, token_id=token.id if token else None, note=(payload or {}).get("note")
    )
    db.add(item)
    db.commit()
    write_audit(actor, "add_watchlist_item", "watchlist_item", item.id, {"mint_address": mint}, db)
    return {"id": item.id, "mint_address": item.mint_address, "note": item.note}


@router.delete("/{watchlist_id}/items/{mint}")
def remove_item(
    watchlist_id: str,
    mint: str,
    db: Session = Depends(get_db),
    actor: str = Depends(require_operator),
):
    item = (
        db.query(WatchlistItem)
        .filter(WatchlistItem.watchlist_id == watchlist_id, WatchlistItem.mint_address == mint)
        .first()
    )
    if item is None:
        raise NotFoundError("watchlist_item", mint)
    db.delete(item)
    db.commit()
    write_audit(actor, "remove_watchlist_item", "watchlist_item", item.id, {"mint_address": mint}, db)
    return {"ok": True, "removed": mint}
