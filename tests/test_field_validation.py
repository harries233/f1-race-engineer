"""Unit tests：字段级校验（range/unit/完整性，全部 WARN，不翻 status）。"""

import pytest

from mock.factory import (
    build_car_telemetry_datagram,
    build_header_bytes,
    build_session_datagram,
)
from protocol.f1_25_2026.field_validate import build_field_validation_chain
from protocol.f1_25_2026.header import parse_header
from protocol.f1_25_2026.payload import (
    CarStatusData,
    CarSetupData,
    CarTelemetryData,
    LapData,
    PacketCarSetupData,
    PacketCarStatusData,
    PacketCarTelemetryData,
    PacketLapData,
    parse_payload,
)
from validate.rules import FrameContext


def _header(packet_id: int = 6):
    return parse_header(build_header_bytes(packet_id=packet_id, player_car_index=0))


def _issues(payload, packet_id: int = 6):
    chain = build_field_validation_chain()
    report = chain.validate(FrameContext(data=b"", header=_header(packet_id), payload=payload))
    return list(report.issues)


def _codes(payload, packet_id: int = 6):
    return [i.code for i in _issues(payload, packet_id)]


# ---------------------------------------------------------------------------
# 构造器：合法的默认模型，便于覆盖个别字段制造越界场景
# ---------------------------------------------------------------------------

def _telemetry(**overrides) -> CarTelemetryData:
    d = dict(
        m_speed=250, m_throttle=0.5, m_steer=0.0, m_brake=0.0, m_clutch=0, m_gear=4,
        m_engineRPM=11000, m_drs=0, m_revLightsPercent=0, m_revLightsBitValue=0,
        m_brakesTemperature=[500] * 4, m_tyresSurfaceTemperature=[90] * 4,
        m_tyresInnerTemperature=[95] * 4, m_engineTemperature=90,
        m_tyresPressure=[23.0] * 4, m_surfaceType=[0] * 4,
    )
    d.update(overrides)
    return CarTelemetryData(**d)


def _telemetry_packet(car=None, **overrides) -> PacketCarTelemetryData:
    d = dict(
        m_carTelemetryData=[car or _telemetry()],
        m_mfdPanelIndex=0, m_mfdPanelIndexSecondaryPlayer=255, m_suggestedGear=4,
    )
    d.update(overrides)
    return PacketCarTelemetryData(**d)


def _lap(**overrides) -> LapData:
    d = dict(
        m_lastLapTimeInMS=92534, m_currentLapTimeInMS=10000,
        m_sector1TimeMSPart=0, m_sector1TimeMinutesPart=0,
        m_sector2TimeMSPart=0, m_sector2TimeMinutesPart=0,
        m_deltaToCarInFrontMSPart=0, m_deltaToCarInFrontMinutesPart=0,
        m_deltaToRaceLeaderMSPart=0, m_deltaToRaceLeaderMinutesPart=0,
        m_lapDistance=0.0, m_totalDistance=0.0, m_safetyCarDelta=0.0,
        m_carPosition=1, m_currentLapNum=1, m_pitStatus=0, m_numPitStops=0,
        m_sector=0, m_currentLapInvalid=0, m_penalties=0, m_totalWarnings=0,
        m_cornerCuttingWarnings=0, m_numUnservedDriveThroughPens=0,
        m_numUnservedStopGoPens=0, m_gridPosition=1, m_driverStatus=0,
        m_resultStatus=0, m_pitLaneTimerActive=0, m_pitLaneTimeInLaneInMS=0,
        m_pitStopTimerInMS=0, m_pitStopShouldServePen=0, m_speedTrapFastestSpeed=0.0,
        m_speedTrapFastestLap=0,
    )
    d.update(overrides)
    return LapData(**d)


def _status(**overrides) -> CarStatusData:
    d = dict(
        m_tractionControl=0, m_antiLockBrakes=0, m_fuelMix=1, m_frontBrakeBias=55,
        m_pitLimiterStatus=0, m_fuelInTank=80.0, m_fuelCapacity=110.0,
        m_fuelRemainingLaps=20.0, m_maxRPM=13000, m_idleRPM=3500, m_maxGears=8,
        m_drsAllowed=0, m_drsActivationDistance=100, m_actualTyreCompound=17,
        m_visualTyreCompound=17, m_tyresAgeLaps=3, m_vehicleFIAFlags=0,
        m_enginePowerICE=800.0, m_enginePowerMGUK=120.0, m_ersStoreEnergy=2000000.0,
        m_ersDeployMode=1, m_ersHarvestedThisLapMGUK=1000.0,
        m_ersHarvestedThisLapMGUH=1000.0, m_ersHarvestLimitPerLap=2000000.0,
        m_ersDeployedThisLap=500000.0, m_networkPaused=0,
    )
    d.update(overrides)
    return CarStatusData(**d)


def _setup(**overrides) -> CarSetupData:
    d = dict(
        m_frontWing=30, m_rearWing=30, m_onThrottle=60, m_offThrottle=50,
        m_frontCamber=-3.0, m_rearCamber=-1.5, m_frontToe=0.1, m_rearToe=0.2,
        m_frontSuspension=10, m_rearSuspension=10, m_frontAntiRollBar=10,
        m_rearAntiRollBar=10, m_frontSuspensionHeight=25, m_rearSuspensionHeight=50,
        m_brakePressure=95, m_brakeBias=55, m_engineBraking=5,
        m_rearLeftTyrePressure=23.0, m_rearRightTyrePressure=23.0,
        m_frontLeftTyrePressure=23.5, m_frontRightTyrePressure=23.5,
        m_ballast=0, m_fuelLoad=40.0,
    )
    d.update(overrides)
    return CarSetupData(**d)


# ---------------------------------------------------------------------------
# 越界 → WARN；合法 → 无 issue；错误类型 → 静默跳过
# ---------------------------------------------------------------------------

def test_telemetry_valid_no_issues():
    assert _issues(_telemetry_packet()) == []


def test_telemetry_out_of_range_warns():
    payload = _telemetry_packet(_telemetry(m_throttle=1.5, m_gear=10))
    assert _codes(payload) == ["field_out_of_range", "field_out_of_range"]


def test_lap_sector_out_of_range_warns():
    payload = PacketLapData(m_lapData=[_lap(m_sector=3)], m_timeTrialPBCarIdx=0,
                            m_timeTrialRivalCarIdx=0)
    assert _codes(payload, packet_id=2) == ["field_out_of_range"]


def test_status_fuelmix_out_of_range_warns():
    payload = PacketCarStatusData(m_carStatusData=[_status(m_fuelMix=5)])
    assert _codes(payload, packet_id=7) == ["field_out_of_range"]


def test_setup_brake_bias_out_of_range_warns():
    payload = PacketCarSetupData(m_carSetupData=[_setup(m_brakeBias=150)],
                                 m_nextFrontWingValue=0.0)
    assert _codes(payload, packet_id=5) == ["field_out_of_range"]


def test_session_weather_out_of_range_warns():
    payload = parse_payload(1, build_session_datagram(weather=9))
    assert _codes(payload, packet_id=1) == ["field_out_of_range"]


def test_unrelated_payload_type_skipped():
    # LapData 规则不该对 Telemetry 模型产出任何 issue（类型自分发）
    assert _issues(_telemetry_packet(), packet_id=2) == []


def test_none_payload_skipped():
    assert _issues(None) == []


# ---------------------------------------------------------------------------
# 端到端：receiver 接线后，越界字段以 WARN 进 validation_issues，status 仍 VALID
# ---------------------------------------------------------------------------

def test_receiver_flags_field_out_of_range_as_warn():
    from ingest.receiver import TelemetryReceiver
    from store.schemas import PacketValidationStatus

    receiver = TelemetryReceiver(port=12345)
    datagram = build_car_telemetry_datagram(speed=999, gear=10)  # 越界
    packet = receiver._to_packet(datagram, ("10.0.0.1", 9999))

    assert packet.validation_status is PacketValidationStatus.VALID
    assert any(i.code == "field_out_of_range" for i in packet.validation_issues)
