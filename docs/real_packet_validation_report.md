# §12 REAL_PACKET_VALIDATION_REPORT — F1 25 2026 Season Pack

> 状态：**通过**（2026-08-13）
> 依据：真实 UDP 帧（Windows 上 F1 25 + 2026 Season Pack，`gameVer=1.24`）
> 抓包：`scripts/capture_udp.py --port 20779 --out capture_udp.bin`（端口由配置传入，非硬编码）

## 1. 验证结论

| 验证项 | 结果 |
|---|---|
| Header = 29 字节，packed，little-endian（`<HBBBBBQfIIBB`） | ✅ 通过 |
| `m_packetFormat` 路由（=2026 → F1_25_2026） | ✅ 通过 |
| 17-packet registry 的 expected_size | ✅ 通过（见 §3） |
| parser.py 的 8 项基础校验 | ✅ 通过 |
| `m_gameYear` | ⚠️ =25（见 §4；Spec `.txt` 注释 "e.g. 26" 为笔误） |

## 2. 抓包环境

- 游戏：F1 25（`gameMajor=1`、`gameMinor=24`），2026 Season Pack（DLC）
- 关键设置：Settings → Telemetry Settings → **UDP Format = 2026**（不是 2025 legacy）
- `sessionUID=12629184837797852754`；抓包时 `sessionTime≈78.8s`、`frameIdentifier=1681`
- `playerCarIndex=0`、`secondaryPlayerCarIndex=255`（无第二玩家，符合预期）

## 3. 尺寸逐项核对（15/17 捕获，全 VALID）

| packetId | 名称 | registry expected_size | 实际 size | 结果 |
|---|---|---|---|---|
| 0 | Motion | 1325 | 1325 | ✅ |
| 1 | Session | 926 | 926 | ✅ |
| 2 | Lap Data | 1399 | 1399 | ✅ |
| 3 | Event | 45 | 45 | ✅ |
| 4 | Participants | 1470 | 1470 | ✅ |
| 5 | Car Setups | 1233 | 1233 | ✅ |
| 6 | Car Telemetry | 1448 | 1448 | ✅ |
| 7 | Car Status | 1445 | 1445 | ✅ |
| 8 | Final Classification | 1134 | —（未捕获） | 比赛结束才发 |
| 9 | Lobby Info | 1062 | —（未捕获） | 联机大厅才发 |
| 10 | Car Damage | 1133 | 1133 | ✅ |
| 11 | Session History | 1460 | 1460 | ✅ |
| 12 | Tyre Sets | 231 | 231 | ✅ |
| 13 | Motion Ex | 273 | 273 | ✅ |
| 14 | Time Trial | 104 | 104 | ✅ |
| 15 | Lap Positions | 1231 | 1231 | ✅ |
| 16 | Car Telemetry 2 | 269 | 269 | ✅ |

> 8（Final Classification）/ 9（Lobby Info）未捕获属**预期**：前者比赛结束一次性发送，后者仅联机大厅。单机练习/计时赛不产生这两帧；比赛结束 / 进联机大厅可补验。

## 4. ⚠️ `m_gameYear` = 25（Spec 笔误记录）

| 来源 | gameYear |
|---|---|
| Spec `.txt`（结构体注释） | "e.g. 26" |
| Spec `.pdf`（正文） | "e.g. 25" |
| **真实 2026-format UDP 数据** | **25** |

**结论**：`m_gameYear=25` 是真实且正确的。2026 Season Pack 是 F1 25 的 DLC，基础游戏仍是 F1 25，所以游戏本体年份为 25；`m_packetFormat=2026` 仅表示**遥测结构体格式**（新布局），与 gameYear 是两个独立字段。因此是 `.txt` 结构体注释的 "e.g. 26" 写错了，`.pdf` 正文的 "e.g. 25" 才对，真实数据印证了 25。

**代码处理**：parser 从真实数据读 `gameYear`（offset 2），无硬编码、无 gameYear 校验 → `gameYear=25` 原样流入，不影响任何校验。**无需改代码。**

## 5. 仍 UNVERIFIED（不写死、不猜）

- 默认 UDP 端口（Spec 无数值；20777 是历史默认，非官方依据）
- Car Damage 频率（正文 10/s vs FAQ 2/s 矛盾）
- 6 个 "Rate as specified in menus" 的 packet 实际 Hz（CONFIGURED_BY_GAME）

## 6. 结论

PHASE 1 接收链（29 字节 header 解析 + packetFormat 路由 + registry size 校验 + 8 项基础校验）在真实 2026-format UDP 数据上**验证通过**。可进入 PHASE 2（校验层）+ PHASE 3（入库）。
