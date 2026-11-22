"""入笼冻结：可用保证金划入笼内，写笼代；含核验升代接口（乙路径）。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from auth import AuthHeader, require_user, require_writer
from db import connect, now_iso, write_audit
from generation_policy import PATH_CODE, assert_locked_path, log_upgrade
from locks import cage_write_guard
from models import CageFreezeIn, GenerationUpgradeIn

router = APIRouter(tags=["cages"])


def _next_cage_code(conn, party_key: str) -> str:
    n = conn.execute(
        "SELECT COUNT(*) c FROM cages WHERE party_key=?", (party_key,)
    ).fetchone()["c"]
    return f"CG-{party_key}-{n + 1:03d}"


@router.get("/api/cages")
def list_cages(authorization: AuthHeader = None, status: str | None = None):
    require_user(authorization)
    with connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM cages WHERE status=? ORDER BY id DESC", (status,)
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM cages ORDER BY id DESC").fetchall()
        return {"items": [dict(r) for r in rows]}


@router.get("/api/cages/{cage_id}")
def get_cage(cage_id: int, authorization: AuthHeader = None):
    require_user(authorization)
    with connect() as conn:
        cage = conn.execute("SELECT * FROM cages WHERE id=?", (cage_id,)).fetchone()
        if not cage:
            raise HTTPException(404, "笼不存在")
        atts = conn.execute(
            """SELECT a.*,
                      CASE WHEN c.current_ticket_ref IS NOT NULL
                           AND a.attest_ref = c.current_ticket_ref
                           THEN 1 ELSE 0 END AS current
               FROM attestations a JOIN cages c ON c.id=a.cage_id
               WHERE a.cage_id=? ORDER BY a.id DESC""",
            (cage_id,),
        ).fetchall()
        rels = conn.execute(
            "SELECT * FROM releases WHERE cage_id=? ORDER BY id DESC",
            (cage_id,),
        ).fetchall()
        fors = conn.execute(
            "SELECT * FROM forfeits WHERE cage_id=? ORDER BY id DESC",
            (cage_id,),
        ).fetchall()
        events = conn.execute(
            "SELECT * FROM generation_events WHERE cage_id=? ORDER BY id DESC",
            (cage_id,),
        ).fetchall()
        return {
            "cage": dict(cage),
            "attestations": [dict(a) for a in atts],
            "releases": [dict(r) for r in rels],
            "forfeits": [dict(f) for f in fors],
            "generation_events": [dict(e) for e in events],
        }


@router.post("/api/cages/freeze")
def freeze_cage(body: CageFreezeIn, authorization: AuthHeader = None):
    """从账户可用余额划入新笼并冻结。"""
    user = require_writer(authorization)
    lock_key = f"bond:{body.party_key}"
    with connect() as conn, cage_write_guard(conn, lock_key, user):
        acct = conn.execute(
            "SELECT * FROM bond_accounts WHERE party_key=?",
            (body.party_key,),
        ).fetchone()
        if not acct:
            raise HTTPException(404, "保证金户不存在")
        if acct["status"] != "正常":
            raise HTTPException(409, "账户状态禁止入笼")
        amount = float(body.amount)
        free = float(acct["balance"]) - float(acct["frozen"])
        if amount > free + 1e-9:
            raise HTTPException(409, "可用保证金不足，无法入笼")
        code = body.cage_code or _next_cage_code(conn, body.party_key)
        dup = conn.execute(
            "SELECT id FROM cages WHERE cage_code=?", (code,)
        ).fetchone()
        if dup:
            raise HTTPException(409, "笼编码已存在")
        now = now_iso()
        cur = conn.execute(
            """INSERT INTO cages(cage_code,party_key,contract_no,amount,available,
               generation,status,beneficiary,created_at,frozen_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                code,
                body.party_key,
                body.contract_no,
                amount,
                amount,
                1,
                "已冻结",
                body.beneficiary,
                now,
                now,
            ),
        )
        cage_id = cur.lastrowid
        conn.execute(
            "UPDATE bond_accounts SET frozen = frozen + ? WHERE party_key=?",
            (amount, body.party_key),
        )
        write_audit(
            conn,
            user,
            "cage_freeze",
            code,
            {
                "cage_id": cage_id,
                "amount": amount,
                "contract_no": body.contract_no,
                "beneficiary": body.beneficiary,
                "generation": 1,
            },
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cages WHERE id=?", (cage_id,)).fetchone()
        return dict(row)


@router.post("/api/cages/{cage_id}/generation-upgrade")
def upgrade_generation(cage_id: int, body: GenerationUpgradeIn, authorization: AuthHeader = None):
    """核验升代（乙路径）：旧结论留史只读，笼代+1 且当前票指针置空，等待新材料重裁。

    抢笼锁：后到者只留争用痕、不写业务。本代已有解笼/罚没落账则拒升，禁止抹账。
    """
    user = require_writer(authorization)
    # 命运锁：只准乙路径，第三路/甲路径请求当场偏航拒写
    assert_locked_path(body.path)
    lock_key = f"cage:{cage_id}"
    with connect() as conn, cage_write_guard(conn, lock_key, user):
        cage = conn.execute(
            "SELECT * FROM cages WHERE id=?", (cage_id,)
        ).fetchone()
        if not cage:
            raise HTTPException(404, "笼不存在")
        if cage["status"] in ("已解笼", "已罚没"):
            raise HTTPException(409, "笼已终结，禁止升代")
        # 本代资金已出笼则禁止升代抹账
        money_out = conn.execute(
            """SELECT COUNT(*) c FROM (
                   SELECT 1 FROM releases
                   WHERE cage_id=? AND cage_generation=? AND status='已拨付'
                   UNION ALL
                   SELECT 1 FROM forfeits
                   WHERE cage_id=? AND cage_generation=? AND status='已罚没'
               )""",
            (cage_id, int(cage["generation"]), cage_id, int(cage["generation"])),
        ).fetchone()["c"]
        if money_out:
            raise HTTPException(409, "本笼代已有解笼/罚没落账，禁止升代抹账")
        from_gen = int(cage["generation"])
        to_gen = from_gen + 1
        old_ticket = cage["current_ticket_ref"]
        conn.execute(
            """UPDATE cages
               SET generation=?, status='已冻结', current_ticket_ref=NULL
               WHERE id=?""",
            (to_gen, cage_id),
        )
        log_upgrade(
            conn,
            user,
            cage_id,
            cage["cage_code"],
            from_gen,
            to_gen,
            old_ticket,
            body.reason,
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cages WHERE id=?", (cage_id,)).fetchone()
        return dict(row)
