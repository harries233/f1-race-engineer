# F1 25 AI Race Engineer — 架构与数据 Schema（v0.1）

> 本文档是项目唯一权威的架构与数据契约。改动设计必须先改这里，再动代码。
> 状态：2026-08-13 建立。PHASE 1（接收层）+ PHASE 2（校验层）+ PHASE 3（入库，SQLite）+ PHASE 4（payload 字段解析 17 结构体 + 字段级校验 + L4 lap/sector 指标）+ PHASE 5（结构化入库）+ PHASE 6/7（Tool 层 + L5 AI 骨架）已落地，§12 真实 UDP 验证通过。未写逐弯分析（CornerRecord，依赖独立赛道数据层）/ A-B 实验（PHASE 8/9）。

---

## 0. 项目定位与边界

| 维度 | 是 | 不是 |
|---|---|---|
| 数据来源 | F1 25 UDP Telemetry 原始帧 | 静态预设（那是 f1-shanghai-setup 的活） |
| 核心链路 | 接收 → 校验 → 入库 → 确定性计算 → AI 分析 → 推荐 → A/B 验证 | 聊天式 F1 知识问答 |
| 结论依据 | 可追溯的 source/timestamp/unit/confidence | LLM 凭感觉给数字 |
| 关系 | 全新独立项目，与 f1-shanghai-setup 无关 | f1-shanghai-setup App 的延伸 |

技术栈：**Python**（数据层 + 后续 ML）。数据 Schema 用 **Pydantic v2**。

---

## 1. 分层架构（对应 PHASE 1–11）

```
┌─────────────────────────────────────────────────┐
│ L5  AI Race Engineer (Agent + Tools)      PH6-7 │  ← 只通过 Tool 层读数据
│       get_telemetry / get_lap / ... / validate_setup
├─────────────────────────────────────────────────┤
│ L4  分析层（确定性计算，非 LLM）          PH4,8,9│  ← Python 函数，不靠模型算
│      lap/sector/corner 指标、compare、validate
├─────────────────────────────────────────────────┤
│ L3  数据层（数据库 + Schema）             PH3   │  ← 唯一可信数据源
│      RawPacket / Lap / Sector / Corner / Setup / Experiment
├─────────────────────────────────────────────────┤
│ L2  校验层                                   PH2 │  ← 完整性/范围/单位/timestamp/异常
├─────────────────────────────────────────────────┤
│ L1  接收层（UDP socket）                    PH1 │  ← 只负责收帧 + 打 source 标签
└─────────────────────────────────────────────────┘
```

硬约束：

- **AI 层永不直接碰 UDP**，也不自己算数。只能调 L4/L3 暴露的 Tool；每个 Tool 返回值带 `source_level`。
- **LLM 不是计算器**：所有 `calculate_*`、`compare_*` 在 L4 用纯 Python 实现，AI 只做「读结果 + 归纳 + 给置信度」。
- **Mock 数据物理隔离**：`tests/mock/`，永远不进 L1 生产接收路径，且标 `MOCK_DATA`。

---

## 2. 通用数据信封（所有实体强制内嵌）

每个持久化记录都带这 5 个字段（Pydantic 基类 `Stamped`）：

```python
{
  "source_level": "RAW | DERIVED | GAME_DATA | VALIDATED | MODEL | HYPOTHESIS",
  "source":       "udp:packet:car_telemetry | calc:corner_metrics | game:ea_udp_spec | test:exp#001",
  "timestamp":    "2026-08-13T09:00:00.000Z",   # 统一 UTC ISO8601 + 帧内 sessionTime
  "unit":         "m/s | km/h | ° | % | psi | ...",
  "confidence":   "HIGH | MEDIUM | LOW",
}
```

- `source_level` 即优先级序：**RAW > DERIVED > GAME_DATA > VALIDATED > MODEL > HYPOTHESIS**。
- 冲突时按 `source_level` 仲裁；无法仲裁 → 输出 `DATA_CONFLICT`，并列明「谁 vs 谁 + 谁更可信 + 是否影响结论」。

---

## 3. 实体 Schema

完整字段定义见 `src/store/schemas.py`（权威）。此处只列结构与派生关系。

| 实体 | 层 | 关键字段 | 备注 |
|---|---|---|---|
| RawPacket | L1 | packet_id / packet_format / session_uid / payload(bytes) | payload 原样保留，不二次加工 |
| Session | L2/L3 | session_uid / track_id / session_type / weather / track_temp / … | 天气/油量/ERS/DRS 上下文 |
| LapRecord | L3+L4 | lap_number / lap_time / sector1-3 / valid_flag / setup_version | setup_version → SetupSnapshot |
| SectorRecord | L4 | sector_time / entry_speed / min_speed / exit_speed | 速度字段 DERIVED |
| CornerRecord | L4 | entry/mid/exit 各指标 + time_loss_phase | 依赖独立赛道数据层（见 §4） |
| SetupSnapshot | L3 | setup_version / params(SetupParams) | 版本化管理，参数清单待确认 |
| Experiment | L4 | exp_id / status / test_conditions / results | BASELINE/TEST 对比与验证 |

**PHASE 5 结构化遥测表**：除上述领域实体外，L3 另有一组「原始遥测投影表」`packet_<name>`（每 packet 类型一张），由 `protocol/f1_25_2026/flatten.py` 把 payload 打平成 `StructuredTable`、`store/structured_store.py` 落库。规则：标量→列、per-car 数组→每车一行（加 `car_index`）、嵌套集合→JSON 文本列；每行带 5 字段信封 + `raw_packets(id)` 外键做可追溯。这些表是 RAW 级投影（`source_level=RAW`、`unit="raw"`），逐字段单位在官方 Spec。

---

## 4. ⚠️ 关键设计依赖：赛道数据层

标准 F1 25 UDP 遥测**不提供**弯角坐标 / 刹车点参考 / 弯角边界。Master Prompt 里的 `get_track` / 逐弯分析依赖一份**独立的赛道数据层**（含几何与参考点，类似 f1-shanghai-setup 的 `TRACK_DETAIL`，但需更完整的几何数据）。

**结论**：赛道数据层必须单独建模块，不塞进 UDP 接收。否则「逐弯分析」会退化成无几何依据的猜测。此模块排期另议，先占位，不阻塞 PHASE 1。

---

## 5. 诚实声明：F1 25 UDP 字段不硬编码

按规则「无法确认就不假设」：

- F1 25 UDP 的 struct 偏移 / 字段名 / 单位，**一律以 EA/Codemasters 官方 F1 25 UDP Spec 为唯一字段来源**（`GAME_DATA`）。
- 无法当场验证的字段标 `TODO(verify)`，禁止进入分析/推荐流程。
- **不生成假帧**；测试数据走 `tests/mock/` + `MOCK_DATA` 标签。

代码里所有 `TODO(verify)` 标记的位置，就是拿到官方 spec 后要补全的清单。

**VERIFIED（2026-08-13，官方 2026 Season Pack Spec）**：Header = 29 字节、Little Endian、packed 无 padding（`struct.unpack('<HBBBBBQfIIBB')`）；17 个 Packet 的 ID/Name/Size 已确认，实现见 `src/protocol/f1_25_2026/`。**UNVERIFIED**：默认 UDP 端口（Spec 未给数值，禁止硬编码 20777，端口必须由配置传入）；Car Damage 频率（Spec 内部矛盾）。

---

## 6. 目录结构

```
f1-race-engineer/
├── docs/architecture.md      # 本文档
├── src/
│   ├── ingest/               # L1 UDP 接收（PHASE 1，已建 receiver.py）
│   ├── validate/             # L2 校验（PHASE 2，已建：框架 + 跨帧校验）
│   ├── store/                # L3 数据库 + Schema（schemas.py + sqlite_store.py +
│   │                         #   structured_store.py 已建）
│   ├── protocol/             # 多协议分层（f1_25_2026 已实现：header/packets/parser/
│   │                         #   validate/structs/payload/field_validate/flatten；
│   │                         #   f1_25_base 占位）
│   ├── analysis/             # L4 确定性计算（lap.py + sector.py 已建）
│   ├── tools/                # L4→L5 Tool 层（PHASE 6/7：registry + get_session/
│   │                         #   get_telemetry/get_lap/list_sessions）
│   └── agent/                # L5 AI 接入骨架（PHASE 7：race_engineer.py 调度器）
├── tests/mock/               # MOCK_DATA，绝不进生产
└── pyproject.toml
```

---

## 7. 关键决策记录

| # | 决策 | 理由 |
|---|---|---|
| 1 | 全新独立项目，Python | 遥测是重后端（UDP+DB+AI+ML），与静态 WebView App 架构差异大 |
| 2 | Schema 用 Pydantic v2 | 直接服务 PHASE 2 校验、PHASE 3 序列化；枚举约束 source_level/confidence |
| 3 | 数据信封强制 5 字段 | 落实「NO DATA → NO FACT」可追溯性 |
| 4 | F1 25 UDP 字段不硬编码 | 防止把未验证字段当事实，标 TODO(verify) 待官方 spec |
| 5 | 赛道数据层独立模块 | UDP 不含弯角几何，逐弯分析必须另建数据层 |
