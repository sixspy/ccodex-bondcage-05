"""审计只读面。"""
from __future__ import annotations

from fastapi import APIRouter

from auth import AuthHeader, require_user
from db import connect
from generation_policy import PATH_CODE, PATH_NAME

router = APIRouter(tags=["audit"])


@router.get("/api/audit")
def list_audit(authorization: AuthHeader = None, limit: int = 100):
    require_user(authorization)
    limit = max(1, min(int(limit), 500))
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_trail ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/audit/actions")
def list_actions(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT action, COUNT(*) c FROM audit_trail
               GROUP BY action ORDER BY c DESC"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/generation-events")
def list_generation_events(authorization: AuthHeader = None):
    """升代事件流水：与审计页、核验页同源。"""
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT g.*, c.cage_code
               FROM generation_events g
               JOIN cages c ON c.id=g.cage_id
               ORDER BY g.id DESC LIMIT 200"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/generation-fate")
def generation_fate(authorization: AuthHeader = None):
    """命运锁只读声明：乙路径当日锁死，五页共用此口径。"""
    require_user(authorization)
    return {
        "path_code": PATH_CODE,
        "path_name": PATH_NAME,
        "locked_date": "2026-11-22",
        "rule": "旧票留史只读；解笼/罚没写口只认 cages.current_ticket_ref 新票指针",
        "doc": "docs/核验升代命运说明.md",
    }
