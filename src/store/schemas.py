"""数据层 Schema 定义（PHASE 1-3 的字段契约，权威来源）。

本文件是「数据 Schema」的唯一权威定义。所有持久化记录必须满足：
  1. 强制内嵌数据信封：source_level / source / timestamp / unit / confidence。
  2. source_level 优先级（高→低）：RAW > DERIVED > GAME_DATA > VALIDATED > MODEL > HYPOTHESIS。
  3. 冲突仲裁按 source_level；无法仲裁 → 上层输出 DATA_CONFLICT。
  4. 标 TODO(verify) 的字段：尚未对照官方 EA F1 25 UDP Spec 确认，禁止当作已验证事实。

依赖：pydantic >= 2.0（见 pyproject.toml）。
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# 数据来源等级 & 置信度
# ---------------------------------------------------------------------------

class SourceLevel(str, Enum):
    RAW = "RAW"                # 直接来自 F1 25 UDP Telemetry 原始帧
    DERIVED = "DERIVED"        # 由 RAW 经确定性计算得到
    GAME_DATA = "GAME_DATA"    # 可靠的 F1 25 游戏数据/规则/参数
    VALIDATED = "VALIDATED"    # 经用户实际测试验证
    MODEL = "MODEL"            # 物理/预测模型输出
    HYPOTHESIS = "HYPOTHESIS"  # AI 推断假设


class Confidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ValidationStatus(str, Enum):
    """Setup 验证状态（Master Prompt §13）。"""
    PREDICTED = "PREDICTED"
    TESTING = "TESTING"
    VALIDATED = "VALIDATED"
    PARTIALLY_VALIDATED = "PARTIALLY_VALIDATED"
    NOT_VALIDATED = "NOT_VALIDATED"
    INCONCLUSIVE = "INCONCLUSIVE"


class ProtocolVersion(str, Enum):
    """协议版本。当前只实现 2026 Season Pack；F1 25 本体作为未来占位。"""

    F1_25_2026 = "F1_25_2026"   # packet_format = 2026（2026 Season Pack）
    F1_25_BASE = "F1_25_BASE"   # packet_format = 2025（F1 25 本体，未实现）

    @classmethod
    def from_packet_format(cls, packet_format: int) -> Optional["ProtocolVersion"]:
        """由 UDP header 的 m_packetFormat 识别协议版本；未知返回 None。"""
        if packet_format == 2026:
            return cls.F1_25_2026
        if packet_format == 2025:
            return cls.F1_25_BASE
        return None


class PacketValidationStatus(str, Enum):
    """单帧 UDP datagram 的基础校验结果（VALID / VALIDATION_FAILED）。"""

    VALID = "VALID"
    VALIDATION_FAILED = "VALIDATION_FAILED"


# ---------------------------------------------------------------------------
# 数据信封
# ---------------------------------------------------------------------------

class Stamped(BaseModel):
    """数据信封：任何持久化记录都必须带这 5 个字段。"""

    source_level: SourceLevel
    source: str                          # 具体来源标识，如 "udp:packet:car_telemetry"
    timestamp: str                       # UTC ISO8601；对帧数据含 sessionTime
    unit: str                            # 本条记录主量纲单位
    confidence: Confidence


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# L1 — 原始帧
# ---------------------------------------------------------------------------

class PacketHeader(BaseModel):
    """F1 25: 2026 Season Pack 的 29 字节包头（packed, little-endian）。

    字段顺序与官方 Spec 的 struct PacketHeader 严格一致（见 docs/architecture.md）。
    """

    m_packetFormat: int                     # 应为 2026
    m_gameYear: int                         # 真实 UDP 数据，禁止硬编码
    m_gameMajorVersion: int
    m_gameMinorVersion: int
    m_packetVersion: int                    # 应为 1
    m_packetId: int                         # 0–16
    m_sessionUID: int
    m_sessionTime: float
    m_frameIdentifier: int
    m_overallFrameIdentifier: int
    m_playerCarIndex: int
    m_secondaryPlayerCarIndex: int          # 255 = 无第二玩家


class ValidationIssueRecord(BaseModel):
    """单条校验问题（L2 校验报告的持久化表示，随 RawPacket 流入 L3）。

    severity 用 str（"ERROR"/"WARN"/"INFO"），与 validate 层 Severity 的 value 对齐；
    本文件不重复自建枚举，避免 store → validate 反向依赖。
    """

    code: str       # 稳定机器码，如 "packet_size_mismatch"
    severity: str   # "ERROR" | "WARN" | "INFO"
    message: str    # 人类可读


class RawPacket(Stamped):
    """L1 产出：一帧原始 UDP datagram。

    payload 原样保留（原始 bytes，禁止二次加工）；校验失败也保留原始 datagram，
    不丢弃、不截断、不补零、不自动修复。datagram < 29 字节时 header 为 None。
    validation_issues 承载 L2 校验报告明细，随帧一起流入 L3 入库。
    """

    protocol_version: Optional[ProtocolVersion] = None
    header: Optional[PacketHeader] = None
    payload: bytes
    received_at: str                        # 实际接收时间（UTC ISO8601）
    source_address: Optional[str] = None    # recvfrom 返回的源地址 "ip:port"
    validation_status: PacketValidationStatus = PacketValidationStatus.VALIDATION_FAILED
    validation_issues: list[ValidationIssueRecord] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# L2/L3 — 会话上下文
# ---------------------------------------------------------------------------

class Session(Stamped):
    """会话/比赛条件上下文（Master Prompt §16：天气、油量、ERS、DRS 等）。"""

    session_uid: int
    track_id: str
    session_type: str                      # TODO(verify) practice/quali/race/time_trial 枚举值
    weather: str                           # TODO(verify) 枚举值
    track_temp: Optional[float] = None     # TODO(verify) 单位
    air_temp: Optional[float] = None       # TODO(verify) 单位
    track_wetness: Optional[int] = None    # TODO(verify) 值域
    fuel_mix: Optional[str] = None         # TODO(verify)
    ers_mode: Optional[str] = None         # TODO(verify)
    drs_allowed: Optional[bool] = None     # TODO(verify)


# ---------------------------------------------------------------------------
# L3 + L4 — 圈速 / 分段时间
# ---------------------------------------------------------------------------

class LapRecord(Stamped):
    """单圈记录。速度类 DERIVED 字段由 L4 计算后回填。"""

    lap_number: int
    session_uid: int
    lap_time: Optional[float] = None       # 秒，RAW
    sector1: Optional[float] = None        # 秒，RAW
    sector2: Optional[float] = None        # 秒，RAW
    sector3: Optional[float] = None        # 秒，RAW
    valid_flag: Optional[bool] = None      # 有效圈（进站/切弯/碰撞 → False）
    fuel_load: Optional[float] = None      # TODO(verify) 单位（升/比例）
    tyre_compound: Optional[str] = None    # TODO(verify) 枚举
    tyre_age_laps: Optional[int] = None
    setup_version: Optional[str] = None    # 外键 → SetupSnapshot.setup_version


class SectorRecord(Stamped):
    """分段时间与关键速度点。速度字段为 DERIVED。"""

    lap_number: int
    sector_index: int
    sector_time: Optional[float] = None    # 秒，RAW
    entry_speed: Optional[float] = None    # DERIVED
    min_speed: Optional[float] = None      # DERIVED
    exit_speed: Optional[float] = None     # DERIVED


# ---------------------------------------------------------------------------
# L4 — 弯角（依赖独立赛道数据层，见 architecture.md §4）
# ---------------------------------------------------------------------------

class CornerRecord(Stamped):
    """逐弯指标，全部 DERIVED。弯角几何/参考点来自独立赛道数据层。"""

    track_id: str
    corner_number: int
    entry_braking_point: Optional[float] = None      # DERIVED，米
    entry_brake_pressure: Optional[float] = None     # DERIVED，%
    entry_brake_release: Optional[float] = None      # DERIVED，时间点
    entry_speed: Optional[float] = None              # DERIVED
    mid_min_speed: Optional[float] = None            # DERIVED
    mid_steering: Optional[float] = None             # DERIVED
    mid_throttle: Optional[float] = None             # DERIVED
    mid_stability: Optional[float] = None            # DERIVED
    exit_throttle_application: Optional[float] = None  # DERIVED
    exit_traction: Optional[float] = None            # DERIVED
    exit_speed: Optional[float] = None               # DERIVED
    exit_gear: Optional[int] = None                  # DERIVED
    time_loss_phase: Optional[str] = None            # DERIVED: ENTRY|MID|EXIT


# ---------------------------------------------------------------------------
# L3 — Setup（版本化管理）
# ---------------------------------------------------------------------------

class SetupParams(BaseModel):
    """F1 25 Car Setup 参数。

    TODO(verify): 每个字段的存在性、单位、值域均需官方 spec 或游戏内 Setup 页面交叉确认。
    范围参考（已在你 f1-shanghai-setup 项目验证，GAME_DATA，仅供交叉核对）：
      差速 10–100%、前轮倾角 -3.5°~-2.5°/后轮 -2°~-1°、前束 0.00–0.20°/后束 0.10–0.25°、
      弹簧刚度 1–41、防倾杆 1–21、前底盘 15–35/后底盘 40–60、
      前胎压 22.5–29.5 psi / 后胎压 20.5–26.5 psi。
    """

    front_wing: Optional[int] = None
    rear_wing: Optional[int] = None
    differential_on_throttle: Optional[int] = None
    differential_off_throttle: Optional[int] = None
    front_camber: Optional[float] = None            # °
    rear_camber: Optional[float] = None             # °
    front_toe: Optional[float] = None               # °
    rear_toe: Optional[float] = None                # °
    front_suspension: Optional[int] = None          # 1–41（软→硬）
    rear_suspension: Optional[int] = None           # 1–41（软→硬）
    front_arb: Optional[int] = None                 # 1–21（软→硬）
    rear_arb: Optional[int] = None                  # 1–21（软→硬）
    front_ride_height: Optional[int] = None         # mm（前底盘 15–35）
    rear_ride_height: Optional[int] = None          # mm（后底盘 40–60）
    brake_bias: Optional[float] = None              # % 前刹占比
    brake_pressure: Optional[float] = None          # %
    front_tyre_pressure: Optional[float] = None     # psi
    rear_tyre_pressure: Optional[float] = None      # psi


class SetupSnapshot(Stamped):
    """一次 Setup 快照，版本化。每个 Experiment 引用 baseline/test 两个版本。"""

    setup_version: str
    track_id: str
    name: str
    params: SetupParams


# ---------------------------------------------------------------------------
# L4 — 实验 / A/B 验证
# ---------------------------------------------------------------------------

class TestConditions(BaseModel):
    """A/B 测试必须记录的条件（Master Prompt §12 完整清单）。"""

    fuel: Optional[str] = None
    tyre_compound: Optional[str] = None
    weather: Optional[str] = None
    track_temp: Optional[float] = None
    track_evolution: Optional[str] = None
    traffic: Optional[str] = None
    ers: Optional[str] = None
    drs: Optional[str] = None
    damage: Optional[str] = None
    session_type: Optional[str] = None


class Experiment(Stamped):
    """一次 Setup 实验：BASELINE vs TEST → RESULT。"""

    exp_id: str
    hypothesis: str
    setup_baseline_version: str
    setup_test_version: str
    status: ValidationStatus = ValidationStatus.PREDICTED
    test_conditions: TestConditions = Field(default_factory=TestConditions)
    baseline_laps: list[int] = Field(default_factory=list)   # lap_number 集合
    test_laps: list[int] = Field(default_factory=list)
    delta_metrics: dict = Field(default_factory=dict)        # 确定性计算产出的对比指标
