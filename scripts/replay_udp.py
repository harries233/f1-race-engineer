"""把库里已入库的【真实帧】按时间顺序回放到 UDP 目标（排障 / 无游戏时验证链路）。

数据来源是 raw_packets 表里原样保留的 datagram BLOB（游戏真实发出的字节），
不是 mock、不是合成数据 —— 回放走的是与游戏完全相同的 UDP → 校验 → 入库 →
WS 广播路径，因此可以不开游戏就验证「手机 App 实时遥测」整条链路。

用法：
    python scripts/replay_udp.py --db telemetry.sqlite3 --target 127.0.0.1:20777
    python scripts/replay_udp.py --db telemetry.sqlite3 --target 127.0.0.1:20778 --session-uid 5390921909032255201 --rate 20 --loop

- `--session-uid` 缺省 = 帧数最多的那个会话。
- `--rate` 每秒发送帧数（缺省 20，与游戏 sendRate 一致）。
- `--loop` 循环回放（Ctrl+C 停止）；缺省放完即退出。
- 回放帧的 source_address 是 127.0.0.1:<本进程临时端口>，入库后与游戏直发帧不可区分，
  因此排障验证请配合独立的演示后端 + 演示库使用（见 scripts/../demo.bat），
  避免把回放帧混进生产库。
"""

from __future__ import annotations

import argparse
import socket
import sqlite3
import sys
import time


def iter_frames(db: str, session_uid: int | None) -> list[bytes]:
    """按接收时间顺序取出一个会话的全部原始 datagram BLOB。"""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        if session_uid is None:
            session_uid = con.execute(
                "SELECT session_uid FROM raw_packets "
                "WHERE session_uid != 0 GROUP BY session_uid "
                "ORDER BY COUNT(*) DESC LIMIT 1"
            ).fetchone()
            if session_uid is None:
                raise SystemExit("库中没有 session_uid != 0 的有效帧（只有空闲心跳）")
            session_uid = session_uid[0]
        rows = con.execute(
            "SELECT payload FROM raw_packets WHERE session_uid = ? "
            "ORDER BY received_at, id",
            (session_uid,),
        ).fetchall()
    finally:
        con.close()
    if not rows:
        raise SystemExit(f"会话 {session_uid} 没有任何帧")
    print(f"会话 {session_uid}：共 {len(rows)} 帧，全部为游戏真实发出的原始字节")
    return [r[0] for r in rows]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default="telemetry.sqlite3", help="源数据库（只读打开）")
    ap.add_argument("--target", default="127.0.0.1:20777", help="回放目标 host:port")
    ap.add_argument("--session-uid", type=int, default=None, help="要回放的会话（缺省取帧数最多）")
    ap.add_argument("--rate", type=float, default=20.0, help="每秒发送帧数")
    ap.add_argument("--max-frames", type=int, default=None, help="最多回放前 N 帧（测试用；缺省全部）")
    ap.add_argument("--loop", action="store_true", help="循环回放直到 Ctrl+C")
    args = ap.parse_args()

    host, _, port_s = args.target.partition(":")
    port = int(port_s)
    frames = iter_frames(args.db, args.session_uid)
    if args.max_frames is not None:
        frames = frames[: args.max_frames]
        print(f"测试模式：只回放前 {args.max_frames} 帧")
    interval = 1.0 / args.rate if args.rate > 0 else 0.0

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sent = 0
    t0 = time.monotonic()
    print(f"回放目标 udp://{args.target}，速率 {args.rate} 帧/秒（Ctrl+C 停止）")
    try:
        while True:
            for frame in frames:
                sock.sendto(frame, (host, port))
                sent += 1
                if sent % 200 == 0:
                    el = time.monotonic() - t0
                    print(f"  已回放 {sent} 帧（{sent / el:.1f} 帧/秒）", flush=True)
                if interval:
                    time.sleep(interval)
            if not args.loop:
                break
            print("  —— 一轮回放结束，循环重播 ——")
    except KeyboardInterrupt:
        pass
    finally:
        sock.close()
    print(f"完成：共回放 {sent} 帧 → {args.target}")


if __name__ == "__main__":
    main()
