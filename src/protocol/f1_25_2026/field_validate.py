"""F1_25_2026 字段级校验（PHASE 4）。

payload 解析出的类型化字段，按官方 Spec 注释的显式值域做 range/unit 校验。
复用 `validate/rules.py` 的 `ValidationRule` 扩展点（`FrameContext -> list[ValidationIssue]`），
规则通过 `ctx.payload` 拿字段，`ctx.header` 拿玩家车索引。

严重级策略：
  - 全部 WARN：字段超出合法值域 / 单位不合理，帧仍 VALID（保留，不丢弃）。
  - 无 ERROR 规则：payload 无法解析时 `parse_payload` 已返回 None，由 receiver
    把该帧判 VALIDATION_FAILED，不在此重复。

值域来源：
  - Spec 注释显式给出（如 throttle 0.0–1.0、gear -1..8、sector 0..2）→ 严格校验。
  - 明确暗示的百分比字段（brakeBias/brakePressure 0–100）→ 校验。
  - 无依据的不硬编（如 frontWing 无官方值域 → 不校验）。
  - speed 上界 400 km/h 是 sanity 上限（F1 现实极速 ~370），非 Spec 数值，已标注。
"""

from __future__ import annotations

from protocol.f1_25_2026.payload import (
    CarStatusData,
    CarSetupData,
    CarTelemetryData,
    LapData,
    PacketCarSetupData,
    PacketCarStatusData,
    PacketCarTelemetryData,
    PacketLapData,
    PacketSessionData,
)
from validate.report import Severity, ValidationIssue
from validate.rules import FrameContext, ValidationChain, ValidationRule


def _player_entry(entries: list, ctx: FrameContext):
    """取玩家车的条目；列表为空或索引越界时返回 None。"""
    if not entries:
        return None
    idx = ctx.header.m_playerCarIndex if ctx.header is not None else 0
    if 0 <= idx < len(entries):
        return entries[idx]
    return None


def _range_issue(field: str, value, lo, hi) -> ValidationIssue | None:
    """值超出 [lo, hi] 时生成一条 WARN；否则 None。"""
    if value < lo or value > hi:
        return ValidationIssue(
            "field_out_of_range",
            Severity.WARN,
            f"{field}={value} outside expected range [{lo}, {hi}]",
        )
    return None


def _collect(issues: list[ValidationIssue], *candidates: ValidationIssue | None) -> None:
    for c in candidates:
        if c is not None:
            issues.append(c)


# ---------------------------------------------------------------------------
# Car Telemetry（packet 6）
# ---------------------------------------------------------------------------

def _rule_telemetry_ranges(ctx: FrameContext) -> list[ValidationIssue]:
    if not isinstance(ctx.payload, PacketCarTelemetryData):
        return []
    entry = _player_entry(ctx.payload.m_carTelemetryData, ctx)
    if entry is None:
        return []
    issues: list[ValidationIssue] = []
    _collect(
        issues,
        _range_issue("throttle", entry.m_throttle, 0.0, 1.0),
        _range_issue("steer", entry.m_steer, -1.0, 1.0),
        _range_issue("brake", entry.m_brake, 0.0, 1.0),
        _range_issue("clutch", entry.m_clutch, 0, 100),
        _range_issue("gear", entry.m_gear, -1, 8),
        _range_issue("speed", entry.m_speed, 0, 400),  # 上界 sanity，非 Spec 数值
    )
    return issues


# ---------------------------------------------------------------------------
# Lap Data（packet 2）
# ---------------------------------------------------------------------------

def _rule_lap_ranges(ctx: FrameContext) -> list[ValidationIssue]:
    if not isinstance(ctx.payload, PacketLapData):
        return []
    entry = _player_entry(ctx.payload.m_lapData, ctx)
    if entry is None:
        return []
    issues: list[ValidationIssue] = []
    _collect(
        issues,
        _range_issue("sector", entry.m_sector, 0, 2),
        _range_issue("currentLapInvalid", entry.m_currentLapInvalid, 0, 1),
        _range_issue("pitStatus", entry.m_pitStatus, 0, 2),
    )
    return issues


# ---------------------------------------------------------------------------
# Car Status（packet 7）
# ---------------------------------------------------------------------------

def _rule_status_ranges(ctx: FrameContext) -> list[ValidationIssue]:
    if not isinstance(ctx.payload, PacketCarStatusData):
        return []
    entry = _player_entry(ctx.payload.m_carStatusData, ctx)
    if entry is None:
        return []
    issues: list[ValidationIssue] = []
    _collect(
        issues,
        _range_issue("fuelMix", entry.m_fuelMix, 0, 3),
        _range_issue("tractionControl", entry.m_tractionControl, 0, 2),
        _range_issue("drsAllowed", entry.m_drsAllowed, 0, 1),
        _range_issue("ersDeployMode", entry.m_ersDeployMode, 0, 3),
    )
    return issues


# ---------------------------------------------------------------------------
# Car Setups（packet 5）
# ---------------------------------------------------------------------------

def _rule_setup_ranges(ctx: FrameContext) -> list[ValidationIssue]:
    if not isinstance(ctx.payload, PacketCarSetupData):
        return []
    entry = _player_entry(ctx.payload.m_carSetupData, ctx)
    if entry is None:
        return []
    issues: list[ValidationIssue] = []
    _collect(
        issues,
        _range_issue("brakePressure", entry.m_brakePressure, 0, 100),  # 百分比
        _range_issue("brakeBias", entry.m_brakeBias, 0, 100),          # 百分比
    )
    return issues


# ---------------------------------------------------------------------------
# Session（packet 1）
# ---------------------------------------------------------------------------

def _rule_session_ranges(ctx: FrameContext) -> list[ValidationIssue]:
    if not isinstance(ctx.payload, PacketSessionData):
        return []
    payload = ctx.payload
    issues: list[ValidationIssue] = []
    _collect(
        issues,
        _range_issue("weather", payload.m_weather, 0, 5),  # 0=clear..5=storm
    )
    return issues


def build_field_validation_chain() -> ValidationChain:
    """构造字段级校验链（无状态，规则按 payload 类型自分发）。"""
    rules: list[ValidationRule] = [
        _rule_telemetry_ranges,
        _rule_lap_ranges,
        _rule_status_ranges,
        _rule_setup_ranges,
        _rule_session_ranges,
    ]
    return ValidationChain(rules)
