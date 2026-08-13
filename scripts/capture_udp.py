"""抓取 F1 25 2026 Season Pack 真实 UDP 帧（PHASE 1 真实数据验证工具）。

用法（先激活 .venv）：
    python scripts\\capture_udp.py --port 20777 --out capture_udp.bin

- 端口必须显式传入（官方 Spec 未给默认端口，禁止硬编码）。
- 游戏端（F1 25 → Telemetry Settings → UDP Telemetry = ON）把数据发到本机同一端口。
- 每种 packet_id 只打印第一帧（去重），并把完整 header 字段输出成可复制文本；
  原始 datagram 仍以 [4 字节大端长度][raw bytes] 追加写入 --out。
- Ctrl-C 停止，正常 flush 并关闭文件。
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from ingest.receiver import TelemetryReceiver  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", type=int, required=True, help="本机监听端口（游戏端填同一端口）")
    ap.add_argument("--host", default="0.0.0.0", help="监听地址，默认所有网卡")
    ap.add_argument("--out", default="capture_udp.bin", help="原始帧输出文件")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    out = Path(args.out)
    count = 0
    seen: set[int] = set()  # 每种 packet_id 只打印第一帧（去重，便于复制文本）

    with out.open("wb") as fh:

        def on_packet(pkt) -> None:
            nonlocal count
            fh.write(len(pkt.payload).to_bytes(4, "big"))
            fh.write(pkt.payload)
            count += 1

            h = pkt.header
            if h is None:
                print(
                    f"[{count:5d}] {pkt.source_address}  header=None  "
                    f"size={len(pkt.payload)}  {pkt.validation_status.value}",
                    flush=True,
                )
                return

            if h.m_packetId in seen:
                return
            seen.add(h.m_packetId)

            print(
                f"packetId={h.m_packetId:<2d} size={len(pkt.payload):4d} "
                f"{pkt.validation_status.value} | packetFormat={h.m_packetFormat} "
                f"gameYear={h.m_gameYear} gameVer={h.m_gameMajorVersion}.{h.m_gameMinorVersion} "
                f"packetVersion={h.m_packetVersion} sessionUID={h.m_sessionUID} "
                f"sessionTime={h.m_sessionTime:.3f} frameIdentifier={h.m_frameIdentifier} "
                f"overallFrameIdentifier={h.m_overallFrameIdentifier} "
                f"playerCarIndex={h.m_playerCarIndex} "
                f"secondaryPlayerCarIndex={h.m_secondaryPlayerCarIndex}",
                flush=True,
            )

        rx = TelemetryReceiver(host=args.host, port=args.port, on_packet=on_packet)
        print(f"listening on {args.host}:{args.port} ... (Ctrl-C 停止)", flush=True)
        try:
            rx.serve_forever()
        except KeyboardInterrupt:
            pass

    print(f"\n抓到 {count} 帧，已写入 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
