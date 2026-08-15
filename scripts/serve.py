"""启动常驻服务（PHASE 14）：UDP receiver + FastAPI 服务层。

用法（先激活 .venv）：
    python scripts/serve.py --db telemetry.sqlite3 --port 8000 [--udp-port 20777]

- `--udp-port` 缺省时以「只读服务」启动：对已入库数据提供仪表盘 + AI 对话，不监听 UDP
  （回放 / 演示历史数据用）。
- 传 `--udp-port` 时额外启动 UDP 接收线程，把实时遥测落库并经 WebSocket 推给手机。
- 端口必须显式传入（官方 Spec 未给默认 UDP 端口，禁止硬编码）。
- AI 对话 `/api/ask` 依赖 ANTHROPIC_API_KEY 环境变量（ClaudeRaceEngineer 惰性构造）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import uvicorn  # noqa: E402

from ingest.receiver import TelemetryReceiver  # noqa: E402
from server.app import create_app  # noqa: E402
from server.service import Service  # noqa: E402
from store.experiment_store import ExperimentStore  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", default="telemetry.sqlite3", help="SQLite 库文件路径")
    ap.add_argument("--host", default="0.0.0.0", help="HTTP 监听地址，默认所有网卡")
    ap.add_argument("--port", type=int, default=8000, help="HTTP 端口")
    ap.add_argument(
        "--udp-port",
        type=int,
        default=None,
        help="UDP 接收端口（游戏端填同一端口）；缺省不启动 UDP 接收（只读服务）",
    )
    args = ap.parse_args()

    store = ExperimentStore(args.db)
    receiver = None
    if args.udp_port is not None:
        receiver = TelemetryReceiver(port=args.udp_port)

    service = Service(store, receiver=receiver)
    app = create_app(service)
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
