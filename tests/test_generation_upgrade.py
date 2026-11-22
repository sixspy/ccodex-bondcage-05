"""核验升代三红测试（乙路径：旧票留史，写口只认新票指针）。

先造「旧代结论卡住新材料」假绿事故夹具，再实打核验升代接口：
- 步骤一 test_red1_upgrade_allows_re_adjudication：升代无法重裁 → 红
- 步骤二 test_red2_stale_ticket_cannot_drive_release：旧票仍能驱动解笼 → 红
- 步骤三 test_red3_concurrent_upgrade_lock_contention：双会话同升无争用控制 → 红
三红齐后才准改服务；收尾必须全绿。另含真双会话线程争用与罚没侧旧票拒写。
"""
from __future__ import annotations

import threading

import pytest
from fastapi.testclient import TestClient

from app import app
from db import connect, init_db


@pytest.fixture(autouse=True)
def _db(tmp_path, monkeypatch):
    monkeypatch.setattr("db.DB_PATH", tmp_path / "t.db")
    init_db()
    yield


def _auth(c: TestClient, user: str = "admin") -> dict:
    tok = c.post(
        "/api/login", json={"username": user, "password": "123456"}
    ).json()["token"]
    return {"Authorization": "Bearer " + tok}


def _make_fake_green_cage(
    client: TestClient,
    headers: dict,
    code: str = "CG-FAKE-001",
    party: str = "P-FAKE",
) -> dict:
    """假绿事故夹具：旧代已有「通过」结论并据此放行，但新材料表明结论错误。

    现状系统下该结论卡死同笼代（禁止改口），又没有升代接口，
    新材料进不来 —— 页面仍显示核验通过的假绿。
    """
    client.post(
        "/api/bonds",
        headers=headers,
        json={
            "party_key": party,
            "party_name": f"假绿事故方{party}",
            "initial_deposit": 200000,
        },
    )
    cage = client.post(
        "/api/cages/freeze",
        headers=headers,
        json={
            "party_key": party,
            "contract_no": "HT-FAKE-1",
            "amount": 60000,
            "beneficiary": "假绿受益方",
            "cage_code": code,
        },
    ).json()
    old = client.post(
        "/api/attestations",
        headers=headers,
        json={"cage_id": cage["id"], "outcome": "通过", "evidence": "旧代初验通过"},
    )
    assert old.status_code == 200
    # 同代改口被旧规则卡死 —— 假绿的根
    blocked = client.post(
        "/api/attestations",
        headers=headers,
        json={"cage_id": cage["id"], "outcome": "违约", "evidence": "新材料：现场复验不合格"},
    )
    assert blocked.status_code == 409
    return cage


def test_red1_upgrade_allows_re_adjudication():
    """步骤一：升代接口存在并可让新材料重裁，旧代结论不再卡住新核验。"""
    c = TestClient(app)
    h = _auth(c)
    cage = _make_fake_green_cage(c, h)

    up = c.post(f"/api/cages/{cage['id']}/generation-upgrade", headers=h, json={"reason": "新材料复验"})
    assert up.status_code == 200, f"升代接口缺失/失败（现状为 {up.status_code}）"
    body = up.json()
    assert body["generation"] == 2
    assert body["status"] == "已冻结"
    assert body["current_ticket_ref"] is None

    # 新材料在新代重裁为违约 —— 旧代结论不再拦截
    re_att = c.post(
        "/api/attestations",
        headers=h,
        json={"cage_id": cage["id"], "outcome": "违约", "evidence": "新材料：现场复验不合格"},
    )
    assert re_att.status_code == 200
    new_ticket = re_att.json()
    assert new_ticket["attest_gen"] == 2
    assert new_ticket["attest_ref"] == f"ATT-{cage['cage_code']}-g2"
    # 笼当前指针切到新票
    detail = c.get(f"/api/cages/{cage['id']}", headers=h).json()["cage"]
    assert detail["generation"] == 2
    assert detail["current_ticket_ref"] == new_ticket["attest_ref"]
    # 旧票仍可查（乙路径：留史只读）
    atts = c.get("/api/attestations", headers=h).json()["items"]
    old_rows = [a for a in atts if a["attest_ref"] == f"ATT-{cage['cage_code']}-g1"]
    assert len(old_rows) == 1 and old_rows[0]["current"] == 0


def test_red2_stale_ticket_cannot_drive_release():
    """步骤二：升代后旧票号不得再驱动解笼；写口只认当前新票指针。"""
    c = TestClient(app)
    h = _auth(c)
    cage = _make_fake_green_cage(c, h)
    old_ticket = f"ATT-{cage['cage_code']}-g1"

    assert c.post(
        f"/api/cages/{cage['id']}/generation-upgrade",
        headers=h,
        json={"reason": "新材料复验"},
    ).status_code == 200
    new_att = c.post(
        "/api/attestations",
        headers=h,
        json={"cage_id": cage["id"], "outcome": "通过", "evidence": "新代复验通过"},
    ).json()

    # 持旧票打出金：必须偏航拒写
    stale = c.post(
        "/api/releases",
        headers=h,
        json={"cage_id": cage["id"], "ticket_ref": old_ticket},
    )
    assert stale.status_code == 409
    # 旧票没有产生任何拨付
    rels = c.get("/api/releases", headers=h).json()["items"]
    assert all(r["cage_id"] != cage["id"] for r in rels)
    # 偏航留痕
    audits = c.get("/api/audit?limit=200", headers=h).json()["items"]
    assert any(a["action"] == "generation_deviation" for a in audits)

    # 新票驱动成功
    ok = c.post(
        "/api/releases",
        headers=h,
        json={"cage_id": cage["id"], "ticket_ref": new_att["attest_ref"]},
    )
    assert ok.status_code == 200
    assert ok.json()["release_ref"].startswith(f"REL-{cage['cage_code']}-g2")
    recon = c.get(f"/api/reconcile/{cage['cage_code']}", headers=h).json()
    assert recon["balanced"] is True
    assert recon["current_ticket_ref"] == new_att["attest_ref"]


def test_red2b_stale_ticket_cannot_drive_forfeit():
    """罚没侧同口径：升代后旧违约票不得驱动罚没。"""
    c = TestClient(app)
    h = _auth(c)
    c.post(
        "/api/bonds",
        headers=h,
        json={"party_key": "P-FORF", "party_name": "罚没假绿方", "initial_deposit": 50000},
    )
    # 直接造旧代违约笼
    cage = c.post(
        "/api/cages/freeze",
        headers=h,
        json={
            "party_key": "P-FORF",
            "contract_no": "HT-FAKE-F",
            "amount": 10000,
            "beneficiary": "罚没受益方",
            "cage_code": "CG-FAKE-F1",
        },
    ).json()
    old = c.post(
        "/api/attestations",
        headers=h,
        json={"cage_id": cage["id"], "outcome": "违约", "evidence": "旧代违约"},
    ).json()
    assert old["attest_ref"] == f"ATT-{cage['cage_code']}-g1"
    c.post(
        f"/api/cages/{cage['id']}/generation-upgrade",
        headers=h,
        json={"reason": "新材料"},
    )
    new_att = c.post(
        "/api/attestations",
        headers=h,
        json={"cage_id": cage["id"], "outcome": "违约", "evidence": "新代仍违约"},
    ).json()

    stale = c.post(
        "/api/forfeits",
        headers=h,
        json={"cage_id": cage["id"], "ticket_ref": f"ATT-{cage['cage_code']}-g1"},
    )
    assert stale.status_code == 409
    ok = c.post(
        "/api/forfeits",
        headers=h,
        json={"cage_id": cage["id"], "ticket_ref": new_att["attest_ref"]},
    )
    assert ok.status_code == 200
    assert ok.json()["forfeit_ref"].startswith(f"FOR-{cage['cage_code']}-g2")


def test_red3_concurrent_upgrade_lock_contention():
    """步骤三：双会话同升一只笼，后到者抢笼锁失败，只留争用痕，笼代只跳一次。"""
    c = TestClient(app)
    h1 = _auth(c, "admin")
    h2 = _auth(c, "clerk")
    cage = _make_fake_green_cage(c, h1)
    lock_key = f"cage:{cage['id']}"

    # admin 先占住笼锁（模拟先到会话持锁处理中）
    got = c.post("/api/locks/acquire", headers=h1, json={"lock_key": lock_key})
    assert got.status_code == 200
    late = c.post(
        f"/api/cages/{cage['id']}/generation-upgrade",
        headers=h2,
        json={"reason": "clerk 后到"},
    )
    assert late.status_code == 409
    # 笼代未变、无业务写入
    detail = c.get(f"/api/cages/{cage['id']}", headers=h1).json()["cage"]
    assert detail["generation"] == 1
    assert detail["status"] == "核验通过"
    # 只留争用痕
    contention = c.get("/api/contention", headers=h1).json()["items"]
    assert any(x["lock_key"] == lock_key and x["actor"] == "clerk" for x in contention)
    c.post("/api/locks/release", headers=h1, json={"lock_key": lock_key})

    # 锁释放后先到者可正常升代
    ok = c.post(
        f"/api/cages/{cage['id']}/generation-upgrade",
        headers=h1,
        json={"reason": "admin 先到"},
    )
    assert ok.status_code == 200
    assert ok.json()["generation"] == 2


def test_red3b_parallel_upgrades_only_one_wins():
    """真双会话并行打升代接口：恰好一个成功，另一个只留争用痕。"""
    c = TestClient(app)
    h1 = _auth(c, "admin")
    cage = _make_fake_green_cage(c, h1)
    h2 = _auth(c, "clerk")
    results: list[dict] = []
    barrier = threading.Barrier(2)

    def upgrade(headers: dict, actor: str) -> None:
        local = TestClient(app)
        barrier.wait()
        r = local.post(
            f"/api/cages/{cage['id']}/generation-upgrade",
            headers=headers,
            json={"reason": f"{actor} 并行升代"},
        )
        results.append({"actor": actor, "status": r.status_code})

    t1 = threading.Thread(target=upgrade, args=(h1, "admin"))
    t2 = threading.Thread(target=upgrade, args=(h2, "clerk"))
    t1.start()
    t2.start()
    t1.join(timeout=30)
    t2.join(timeout=30)

    assert sorted(r["status"] for r in results) == [200, 409]
    with connect() as conn:
        gen = conn.execute(
            "SELECT generation FROM cages WHERE id=?", (cage["id"],)
        ).fetchone()["generation"]
        events = conn.execute(
            "SELECT COUNT(*) c FROM generation_events WHERE cage_id=?", (cage["id"],)
        ).fetchone()["c"]
        traces = conn.execute(
            "SELECT COUNT(*) c FROM contention_log WHERE lock_key=?",
            (f"cage:{cage['id']}",),
        ).fetchone()["c"]
    assert gen == 2
    assert events == 1
    assert traces >= 1


def test_upgrade_refused_after_money_left_cage():
    """本代已出金（解笼/罚没落账）不得升代抹账。"""
    c = TestClient(app)
    h = _auth(c)
    cage = _make_fake_green_cage(c, h)
    rel = c.post("/api/releases", headers=h, json={"cage_id": cage["id"]})
    assert rel.status_code == 200
    up = c.post(
        f"/api/cages/{cage['id']}/generation-upgrade",
        headers=h,
        json={"reason": "想抹账"},
    )
    assert up.status_code == 409
