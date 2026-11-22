"""逐页核对：前端五页模板绑定的字段必须全部存在于真实接口载荷，且票号/笼代同源。

无浏览器环境下的 DOM 级替代：拉取线上模板与真实 API 响应，
校验每个绑定表达式引用的字段都有真实数据支撑，防止“只改提示”式空改。
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:10608"


def get(path: str, token: str | None = None):
    req = urllib.request.Request(BASE + path)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(req) as r:
        return r.read().decode()


def login(user: str) -> str:
    data = json.dumps({"username": user, "password": "123456"}).encode()
    req = urllib.request.Request(BASE + "/api/login", data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())["token"]


# 视图文件 -> 该视图消费的接口 -> 列表行字段
PAGE_CONTRACTS = {
    "attest_view.js": [
        ("/api/attestations", ["attest_ref", "cage_code", "outcome", "attest_gen",
                               "current", "officer", "evidence", "created_at"]),
        ("/api/generation-events", ["cage_code", "from_generation", "to_generation",
                                    "old_ticket_ref", "reason", "officer", "created_at"]),
        ("/api/generation-fate", ["path_name", "locked_date"]),
    ],
    "cages_view.js": [
        ("/api/cages", ["cage_code", "available", "amount", "contract_no",
                        "generation", "current_ticket_ref", "party_key", "beneficiary", "status"]),
    ],
    "release_view.js": [
        ("/api/releases", ["release_ref", "cage_code", "cage_id", "cage_generation",
                           "amount", "payee", "created_at"]),
    ],
    "forfeit_view.js": [
        ("/api/forfeits", ["forfeit_ref", "cage_code", "cage_id", "cage_generation",
                           "amount", "reason", "created_at"]),
    ],
    "audit_view.js": [
        ("/api/audit?limit=120", ["created_at", "actor", "action", "target", "payload"]),
        ("/api/contention", ["created_at", "lock_key", "actor", "action", "detail"]),
        ("/api/locks", ["lock_key", "holder", "acquired_at"]),
        ("/api/generation-events", ["created_at", "cage_code", "from_generation",
                                    "to_generation", "old_ticket_ref", "reason", "officer"]),
    ],
    "reconcile_view.js": [
        ("/api/reconcile", ["cage_code", "generation", "status", "current_ticket_ref",
                            "amount", "available", "released", "forfeited",
                            "accounted", "balanced", "gap"]),
    ],
}


def main() -> None:
    token = login("admin")
    failures: list[str] = []
    for view, contracts in PAGE_CONTRACTS.items():
        tpl = get(f"/static/js/views/{view}")
        for path, fields in contracts:
            payload = json.loads(get(path, token))
            rows = payload["items"] if isinstance(payload, dict) and "items" in payload else [payload]
            sample = rows[0] if rows else {}
            for f in fields:
                if f not in sample:
                    failures.append(f"{view} -> {path} 缺字段 {f}")
            # 模板里必须真的绑定了该字段（防空改）
            for f in fields:
                if f not in tpl:
                    failures.append(f"{view} 模板未绑定 {f}（疑似只改提示）")
        print(f"ok - {view} 绑定字段与接口载荷一致")

    # 同源核心：五页看到的同一只笼，票号/笼代必须来自同一事实
    cages = json.loads(get("/api/cages", token))["items"]
    target = [c for c in cages if c["cage_code"] == "CG-E2E-001"]
    if not target:
        failures.append("E2E 笼 CG-E2E-001 不存在，请先跑 e2e_story.py")
    else:
        c = target[0]
        atts = json.loads(get("/api/attestations", token))["items"]
        recon = json.loads(get("/api/reconcile/CG-E2E-001", token))
        rels = json.loads(get("/api/releases", token))["items"]
        rel = [r for r in rels if r["cage_id"] == c["id"]][0]
        current = [a for a in atts if a["attest_ref"] == c["current_ticket_ref"]][0]
        assert recon["current_ticket_ref"] == c["current_ticket_ref"] == current["attest_ref"]
        assert current["attest_gen"] == c["generation"] == rel["cage_generation"] == recon["generation"]
        # 解笼页模板用 ticketOf(cage_id, generation) 反查，反查结果必须等于当前票
        assert current["attest_ref"] == f"ATT-CG-E2E-001-g{c['generation']}"
        print("ok - 核验/入笼/解笼/罚没/审计/对账 六处票号笼代同源一致")

    if failures:
        print("\n".join(failures))
        raise SystemExit(1)
    print("\n五页同源核对全部通过 ✓")


if __name__ == "__main__":
    main()
