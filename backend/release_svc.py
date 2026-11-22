"""解笼拨付：核验通过后把笼内可用额拨付给受益人。

乙路径命运闸门：写口只认 cages.current_ticket_ref 指向的当前笼代票，
旧票/空指针一律记升代偏航并拒写（见 generation_policy）。
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from generation_policy import guard_write_ticket
from locks import cage_write_guard
from models import ReleaseIn

router = APIRouter(tags=["release"])


@router.get("/api/releases")
def list_releases(authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        rows = conn.execute(
            """SELECT r.*, c.cage_code, c.contract_no
               FROM releases r
               JOIN cages c ON c.id=r.cage_id
               ORDER BY r.id DESC LIMIT 200"""
        ).fetchall()
        return {"items": [dict(r) for r in rows]}


@router.post("/api/releases")
def do_release(body: ReleaseIn, authorization: AuthHeader = None):
    user = require_writer(authorization)
    lock_key = f"cage:{body.cage_id}"
    with connect() as conn, cage_write_guard(conn, lock_key, user):
        cage = conn.execute(
            "SELECT * FROM cages WHERE id=?", (body.cage_id,)
        ).fetchone()
        if not cage:
            raise HTTPException(404, "笼不存在")
        if cage["status"] != "核验通过":
            raise HTTPException(409, "仅核验通过的笼可解笼拨付")
        # 命运闸门（乙路径）：写口只认当前票指针，旧票/空指针一律偏航拒写
        att = guard_write_ticket(
            conn, cage, user, body.ticket_ref, write_kind="release"
        )
        if att["outcome"] != "通过":
            raise HTTPException(409, "当前票结论非通过，禁止解笼拨付")
        avail = float(cage["available"])
        amount = float(body.amount) if body.amount is not None else avail
        if amount <= 0:
            raise HTTPException(400, "拨付金额须大于 0")
        if amount > avail + 1e-9:
            raise HTTPException(409, "拨付金额超过笼可用额")
        payee = body.payee or cage["beneficiary"]
        now = now_iso()
        gen = int(cage["generation"])
        ref = f"REL-{cage['cage_code']}-g{gen}-{int(now.replace(':', '').replace('-', '').replace('T', '')[-8:])}"
        cur = conn.execute(
            """INSERT INTO releases(cage_id,amount,payee,cage_generation,status,release_ref,created_at)
               VALUES (?,?,?,?,?,?,?)""",
            (body.cage_id, amount, payee, gen, "已拨付", ref, now),
        )
        new_avail = round(avail - amount, 6)
        new_status = "已解笼" if new_avail <= 1e-9 else "部分解笼"
        conn.execute(
            "UPDATE cages SET available=?, status=? WHERE id=?",
            (max(new_avail, 0.0), new_status, body.cage_id),
        )
        # 账户：冻结减少，余额减少（资金离开系统）
        conn.execute(
            """UPDATE bond_accounts
               SET frozen = frozen - ?, balance = balance - ?
               WHERE party_key=?""",
            (amount, amount, cage["party_key"]),
        )
        write_audit(
            conn,
            user,
            "cage_release",
            cage["cage_code"],
            {
                "release_id": cur.lastrowid,
                "amount": amount,
                "payee": payee,
                "cage_generation": gen,
                "release_ref": ref,
                "ticket_ref": att["attest_ref"],
            },
        )
        conn.commit()
        row = conn.execute(
            "SELECT * FROM releases WHERE id=?", (cur.lastrowid,)
        ).fetchone()
        return dict(row)
