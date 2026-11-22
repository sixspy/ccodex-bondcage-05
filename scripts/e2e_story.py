"""本机 E2E 剧本：对真实 HTTP 端口走完整升代命运链路并逐接口核对五页同源数据。"""
from __future__ import annotations

import json
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:10608"


def call(method: str, path: str, token: str | None = None, body: dict | None = None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode())


def must(cond, msg):
    if not cond:
        raise AssertionError("E2E 失败：" + msg)
    print("  ok -", msg)


def login(user: str) -> str:
    _, r = call("POST", "/api/login", body={"username": user, "password": "123456"})
    return r["token"]


def main() -> None:
    admin = login("admin")
    clerk = login("clerk")
    print("① 登录保留：admin/clerk 均取得令牌")

    print("② 假绿事故夹具 + 升代重裁")
    _, r = call("POST", "/api/bonds", admin, {
        "party_key": "P-E2E", "party_name": "端到端事故方", "initial_deposit": 200000})
    must(r.get("party_key") == "P-E2E", "开户")
    _, cage = call("POST", "/api/cages/freeze", admin, {
        "party_key": "P-E2E", "contract_no": "HT-E2E-1", "amount": 50000,
        "beneficiary": "E2E受益方", "cage_code": "CG-E2E-001"})
    _, old_att = call("POST", "/api/attestations", admin,
                      {"cage_id": cage["id"], "outcome": "通过", "evidence": "旧代初验"})
    must(old_att["attest_ref"] == "ATT-CG-E2E-001-g1", "旧票号 g1 落册")
    code, _ = call("POST", "/api/attestations", admin,
                   {"cage_id": cage["id"], "outcome": "违约", "evidence": "新材料"})
    must(code == 409, "同代改口被拒（假绿根因复现）")

    code, up = call("POST", f"/api/cages/{cage['id']}/generation-upgrade", admin,
                    {"reason": "新材料复验", "path": "B"})
    must(code == 200 and up["generation"] == 2 and up["current_ticket_ref"] is None,
         "升代成功：代2、当前票指针置空")
    code, dev = call("POST", f"/api/cages/{cage['id']}/generation-upgrade", admin,
                     {"reason": "试探甲路径", "path": "A"})
    must(code == 409, "甲路径请求触发命运锁偏航拒写（禁止第三路/混用）")

    _, new_att = call("POST", "/api/attestations", admin,
                      {"cage_id": cage["id"], "outcome": "通过", "evidence": "新代复验通过"})
    must(new_att["attest_ref"] == "ATT-CG-E2E-001-g2", "新票号 g2 落册")

    print("③ 旧票留史只读、写口只认新票")
    _, atts = call("GET", "/api/attestations", admin)
    g1 = [a for a in atts["items"] if a["attest_ref"] == "ATT-CG-E2E-001-g1"][0]
    g2 = [a for a in atts["items"] if a["attest_ref"] == "ATT-CG-E2E-001-g2"][0]
    must(g1["current"] == 0, "查询口仍返回旧票且标记 current=0（留史）")
    must(g2["current"] == 1, "新票标记 current=1")

    code, stale = call("POST", "/api/releases", admin,
                       {"cage_id": cage["id"], "ticket_ref": "ATT-CG-E2E-001-g1"})
    must(code == 409 and "偏航" in stale["detail"], "旧票驱动解笼 → 409 偏航拒写")
    _, rels = call("GET", "/api/releases", admin)
    must(all(x["cage_id"] != cage["id"] for x in rels["items"]), "旧票未产生任何拨付")
    code, rel = call("POST", "/api/releases", admin,
                     {"cage_id": cage["id"], "ticket_ref": "ATT-CG-E2E-001-g2"})
    must(code == 200 and rel["release_ref"].startswith("REL-CG-E2E-001-g2"),
         "新票驱动解笼成功，凭证带 g2")

    print("④ 罚没侧同口径（另开一笼）")
    _, cage2 = call("POST", "/api/cages/freeze", admin, {
        "party_key": "P-E2E", "contract_no": "HT-E2E-2", "amount": 20000,
        "beneficiary": "罚没受益方", "cage_code": "CG-E2E-002"})
    call("POST", "/api/attestations", admin,
         {"cage_id": cage2["id"], "outcome": "违约", "evidence": "g1违约"})
    call("POST", f"/api/cages/{cage2['id']}/generation-upgrade", admin,
         {"reason": "新材料", "path": "B"})
    _, att2 = call("POST", "/api/attestations", admin,
                   {"cage_id": cage2["id"], "outcome": "违约", "evidence": "g2违约"})
    code, _ = call("POST", "/api/forfeits", admin,
                   {"cage_id": cage2["id"], "ticket_ref": f"ATT-CG-E2E-002-g1"})
    must(code == 409, "罚没写口拒收旧票")
    code, frf = call("POST", "/api/forfeits", admin,
                     {"cage_id": cage2["id"], "ticket_ref": att2["attest_ref"]})
    must(code == 200 and frf["forfeit_ref"].startswith("FOR-CG-E2E-002-g2"), "新票罚没成功")

    print("⑤ 双会话同升争用")
    _, cage3 = call("POST", "/api/cages/freeze", admin, {
        "party_key": "P-E2E", "contract_no": "HT-E2E-3", "amount": 10000,
        "beneficiary": "争用受益方", "cage_code": "CG-E2E-003"})
    call("POST", "/api/attestations", admin,
         {"cage_id": cage3["id"], "outcome": "通过", "evidence": "g1"})
    lk = f"cage:{cage3['id']}"
    code, _ = call("POST", "/api/locks/acquire", admin, {"lock_key": lk})
    must(code == 200, "admin 先占笼锁")
    code, late = call("POST", f"/api/cages/{cage3['id']}/generation-upgrade", clerk,
                      {"reason": "clerk后到", "path": "B"})
    must(code == 409 and "争用" in late["detail"], "clerk 后到升代 409")
    _, ct = call("GET", "/api/contention", admin)
    must(any(x["lock_key"] == lk and x["actor"] == "clerk" for x in ct["items"]),
         "争用痕落库（后到只留痕不写业务）")
    call("POST", "/api/locks/release", admin, {"lock_key": lk})
    code, up3 = call("POST", f"/api/cages/{cage3['id']}/generation-upgrade", admin,
                     {"reason": "admin升代", "path": "B"})
    must(code == 200 and up3["generation"] == 2, "锁释放后先到者升代成功")

    print("⑥ 出金后禁升（抹账防护）")
    code, _ = call("POST", f"/api/cages/{cage['id']}/generation-upgrade", admin,
                   {"reason": "想抹账", "path": "B"})
    must(code == 409, "已解笼笼拒绝再升代")

    print("⑦ 五页同源核对")
    _, cages = call("GET", "/api/cages", admin)
    c1 = [x for x in cages["items"] if x["id"] == cage["id"]][0]
    must(c1["generation"] == 2 and c1["current_ticket_ref"] == "ATT-CG-E2E-001-g2",
         "入笼页数据源：笼代2 + 当前票 g2")
    _, detail = call("GET", f"/api/cages/{cage['id']}", admin)
    refs = sorted(a["attest_ref"] for a in detail["attestations"])
    must(refs == ["ATT-CG-E2E-001-g1", "ATT-CG-E2E-001-g2"], "笼详情票册两代齐全")
    must(len(detail["generation_events"]) == 1, "升代事件入笼详情可见")
    _, recon = call("GET", "/api/reconcile/CG-E2E-001", admin)
    must(recon["balanced"] is True and recon["current_ticket_ref"] == "ATT-CG-E2E-001-g2",
         "对账页平衡且当前票指针同源")
    _, events = call("GET", "/api/generation-events", admin)
    must(len(events["items"]) >= 3, "审计页升代事件流水")
    _, audits = call("GET", "/api/audit?limit=300", admin)
    actions = {a["action"] for a in audits["items"]}
    must("generation_deviation" in actions and "generation_upgrade" in actions,
         "审计页可见升代与偏航留痕")
    _, fate = call("GET", "/api/generation-fate", admin)
    must(fate["path_code"] == "B" and fate["locked_date"] == "2026-11-22",
         "命运锁只读声明为乙路径/当日锁死")
    _, viewer = call("POST", "/api/login", body={"username": "viewer", "password": "123456"})
    code, _ = call("POST", f"/api/cages/{cage3['id']}/generation-upgrade", viewer["token"],
                   {"reason": "viewer试探", "path": "B"})
    must(code == 403, "viewer 只读账号禁止升代写口")

    print("\n全部 E2E 核对通过 ✓")


if __name__ == "__main__":
    main()
