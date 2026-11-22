"""本机 E2E 启动器：把库路径切到临时文件，再拉起 uvicorn。

仅用于本机五页核对，不改变后端默认库 data/app.db 的任何行为。
用法：python scripts/run_e2e_server.py <db_path> [port]
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

import db  # noqa: E402

db.DB_PATH = Path(sys.argv[1])
db.init_db()

import uvicorn  # noqa: E402

port = int(sys.argv[2]) if len(sys.argv) > 2 else 10608
uvicorn.run("app:app", host="127.0.0.1", port=port, log_level="warning")
