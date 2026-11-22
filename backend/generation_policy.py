"""核验升代命运：乙路径单一事实源（2026-11-22 当日锁死）。

命运说明见 docs/核验升代命运说明.md。本模块是升代正确性的唯一代码口径：
- 旧票留史只读，查询不拒收、不删除；
- 解笼/罚没写口只认 cages.current_ticket_ref 指向的当前笼代票；
- 任何与命运说明不一致的写口动作记「升代偏航」并拒写（409）。
禁止第三路，禁止甲乙混用。
"""
from __future__ import annotations

import sqlite3

from fastapi import HTTPException

from db import now_iso, write_audit

# 锁定路径：B = 旧票留史，写口只认新票指针
PATH_CODE = "B"
PATH_NAME = "旧票留史·写口只认新票指针"
DEVIATION_ACTION = "generation_deviation"
UPGRADE_ACTION = "generation_upgrade"
TICKET_PREFIX = "ATT"


def build_ticket_ref(cage_code: str, generation: int) -> str:
    """票号格式 ATT-{cage_code}-g{gen}，与命运说明第一节一致。"""
    return f"{TICKET_PREFIX}-{cage_code}-g{int(generation)}"


def assert_locked_path(requested: str) -> None:
    """命运锁：只准乙路径；任何他路请求即偏航拒写。"""
    if requested != PATH_CODE:
        raise HTTPException(409, f"升代偏航：命运已锁乙路径，禁止路径 {requested!r}")


def record_deviation(conn: sqlite3.Connection, actor: str, target: str, detail: dict) -> None:
    """偏航留痕：审计可查，且不产生任何业务金额动作。"""
    write_audit(conn, actor, DEVIATION_ACTION, target, detail)


def current_ticket(conn: sqlite3.Connection, cage) -> sqlite3.Row | None:
    """取笼当前有效票（指针非空才存在）。"""
    ref = cage["current_ticket_ref"] if "current_ticket_ref" in cage.keys() else None
    if not ref:
        return None
    return conn.execute(
        "SELECT * FROM attestations WHERE cage_id=? AND attest_ref=?",
        (cage["id"], ref),
    ).fetchone()


def guard_write_ticket(
    conn: sqlite3.Connection,
    cage,
    actor: str,
    ticket_ref: str | None,
    write_kind: str,
) -> sqlite3.Row:
    """解笼/罚没写口的票号闸门（乙路径核心强制点）。

    规则：
    1. 笼当前票指针为空 → 拒写（升代后尚未重裁）；
    2. 显式传入旧票号（与当前指针不等且确为本笼历史票）→ 偏航拒写留痕；
    3. 传入陌生票号 → 偏航拒写留痕；
    4. 不传票号 → 按当前指针解析；
    5. 票的笼代必须等于笼当前代，结论必须与写口意图一致（由调用方再校 outcome）。
    """
    cage_id = cage["id"]
    pointer = cage["current_ticket_ref"] if "current_ticket_ref" in cage.keys() else None
    if not pointer:
        record_deviation(
            conn,
            actor,
            cage["cage_code"],
            {
                "write_kind": write_kind,
                "reason": "current_ticket_ref_empty",
                "generation": int(cage["generation"]),
                "submitted_ticket": ticket_ref,
            },
        )
        raise HTTPException(409, "升代后尚未重裁：当前票指针为空，禁止解笼/罚没")

    if ticket_ref is not None and ticket_ref != pointer:
        historical = conn.execute(
            "SELECT attest_gen FROM attestations WHERE cage_id=? AND attest_ref=?",
            (cage_id, ticket_ref),
        ).fetchone()
        record_deviation(
            conn,
            actor,
            cage["cage_code"],
            {
                "write_kind": write_kind,
                "reason": "stale_ticket_submitted",
                "submitted_ticket": ticket_ref,
                "current_ticket": pointer,
                "historical_generation": int(historical["attest_gen"]) if historical else None,
                "current_generation": int(cage["generation"]),
            },
        )
        raise HTTPException(409, "升代偏航：旧票不得驱动解笼/罚没，写口只认当前新票")

    ticket = current_ticket(conn, cage)
    if ticket is None:
        record_deviation(
            conn,
            actor,
            cage["cage_code"],
            {
                "write_kind": write_kind,
                "reason": "pointer_dangling",
                "current_ticket": pointer,
            },
        )
        raise HTTPException(409, "升代偏航：当前票指针悬空，拒写")
    if int(ticket["attest_gen"]) != int(cage["generation"]):
        record_deviation(
            conn,
            actor,
            cage["cage_code"],
            {
                "write_kind": write_kind,
                "reason": "ticket_generation_mismatch",
                "ticket_gen": int(ticket["attest_gen"]),
                "cage_generation": int(cage["generation"]),
            },
        )
        raise HTTPException(409, "升代偏航：票笼代不一致，拒写")
    return ticket


def log_upgrade(
    conn: sqlite3.Connection,
    actor: str,
    cage_id: int,
    cage_code: str,
    from_gen: int,
    to_gen: int,
    old_ticket: str | None,
    reason: str,
) -> None:
    """升代事件双留痕：generation_events 业务表 + audit_trail。"""
    conn.execute(
        """INSERT INTO generation_events
           (cage_id,from_generation,to_generation,old_ticket_ref,new_ticket_ref,
            reason,officer,created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (cage_id, from_gen, to_gen, old_ticket, None, reason, actor, now_iso()),
    )
    write_audit(
        conn,
        actor,
        UPGRADE_ACTION,
        cage_code,
        {
            "cage_id": cage_id,
            "from_generation": from_gen,
            "to_generation": to_gen,
            "old_ticket_ref": old_ticket,
            "new_ticket_ref": None,
            "path": PATH_CODE,
            "reason": reason,
        },
    )
