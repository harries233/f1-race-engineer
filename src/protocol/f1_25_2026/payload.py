"""F1_25_2026 payload 类型化解析（PHASE 4）。

把一帧 datagram 的 payload（header 之后的部分）按官方 Spec 结构体解析成类型化
Pydantic 模型。字段名/单位严格照 Spec 注释（km/h、°C、psi、0.0–1.0、-1.0–1.0）。

约束：
  - payload 是「RAW 级」瞬态解析结果，不落库、不带数据信封（信封在 RawPacket 上）。
  - 字段类型照 Spec：uint8=int, int8=int, uint16=int, int16=int, uint32=int,
    float=float, double=float, char[N]=str（UTF-8，去尾 \x00）。
  - 解析失败（短 payload / 未知 packetId / struct 异常）返回 None，由调用方判
    VALIDATION_FAILED，不强行解析。
"""

from __future__ import annotations

import struct
from typing import Optional

from pydantic import BaseModel

from protocol.f1_25_2026.header import HEADER_SIZE
from protocol.f1_25_2026.structs import (
    ACTIVE_AERO_ZONE_FMT,
    CAR_DAMAGE_FMT,
    CAR_MOTION_FMT,
    CAR_SETUP_FMT,
    CAR_STATUS_FMT,
    CAR_TELEMETRY2_FMT,
    CAR_TELEMETRY_FMT,
    DRS_ZONE_FMT,
    EVENT_STRING_CODE_LEN,
    FINAL_CLASSIFICATION_FMT,
    LAP_DATA_FMT,
    LAP_HISTORY_FMT,
    LOBBY_INFO_FMT,
    MARSHAL_ZONE_FMT,
    MAX_ACTIVE_AERO_ZONES,
    MAX_CARS,
    MAX_DRS_ZONES,
    MAX_LAP_HISTORY,
    MAX_LAP_POSITIONS_LAPS,
    MAX_MARSHAL_ZONES,
    MAX_SESSIONS_IN_WEEKEND,
    MAX_TYRE_SETS,
    MAX_TYRE_STINTS,
    MAX_WEATHER_FORECAST,
    PACKET_PAYLOAD_FMT,
    PARTICIPANT_FMT,
    TIME_TRIAL_SET_FMT,
    TYRE_SET_FMT,
    TYRE_STINT_HISTORY_FMT,
    WEATHER_FORECAST_FMT,
)


def _fields(cls: type[BaseModel]) -> tuple[str, ...]:
    """按声明顺序取模型字段名（Pydantic v2 model_fields 保序）。"""
    return tuple(cls.model_fields.keys())


def _size_of(fmt: str) -> int:
    """标准 little-endian packed 尺寸（强制 '<' 前缀，避免 native 对齐 padding）。"""
    return struct.calcsize("<" + fmt.lstrip("<"))


def _from_values(cls: type[BaseModel], values: tuple, arrays: dict[str, int]) -> BaseModel:
    """把扁平 unpack 结果按字段声明顺序构造成模型。

    arrays：字段名 → 元素数，用于把 `4H` 这类数组字段（扁平展开成 4 个标量）
    重新聚合成 list；标量字段按 1 处理。
    """
    d: dict = {}
    i = 0
    for name in _fields(cls):
        n = arrays.get(name, 1)
        d[name] = list(values[i:i + n]) if n > 1 else values[i]
        i += n
    return cls(**d)


def _build_array(
    cls: type[BaseModel],
    fmt: str,
    data: bytes,
    offset: int,
    n: int,
    arrays: dict[str, int] | None = None,
) -> list:
    """连续 unpack n 个同构结构体（如 24 车），构造成模型列表。"""
    arrays = arrays or {}
    size = _size_of(fmt)
    return [
        _from_values(cls, struct.unpack_from("<" + fmt, data, offset + i * size), arrays)
        for i in range(n)
    ]


def _decode_name(raw: bytes) -> str:
    return raw.decode("utf-8", errors="replace").rstrip("\x00")


# ---------------------------------------------------------------------------
# 子结构体模型（per-car / 内嵌）
# ---------------------------------------------------------------------------

class MarshalZone(BaseModel):
    m_zoneStart: float
    m_zoneFlag: int


class ActiveAeroZone(BaseModel):
    m_zoneStart: float
    m_zoneEnd: float


class DRSZone(BaseModel):
    m_zoneStart: float
    m_zoneEnd: float


class WeatherForecastSample(BaseModel):
    m_sessionType: int
    m_timeOffset: int
    m_weather: int
    m_trackTemperature: int
    m_trackTemperatureChange: int
    m_airTemperature: int
    m_airTemperatureChange: int
    m_rainPercentage: int


class CarMotionData(BaseModel):
    m_worldPositionX: float
    m_worldPositionY: float
    m_worldPositionZ: float
    m_worldVelocityX: float
    m_worldVelocityY: float
    m_worldVelocityZ: float
    m_worldForwardDirX: int
    m_worldForwardDirY: int
    m_worldForwardDirZ: int
    m_worldRightDirX: int
    m_worldRightDirY: int
    m_worldRightDirZ: int
    m_gForceLateral: int
    m_gForceLongitudinal: int
    m_gForceVertical: int
    m_yaw: float
    m_pitch: float
    m_roll: float


class LapData(BaseModel):
    m_lastLapTimeInMS: int
    m_currentLapTimeInMS: int
    m_sector1TimeMSPart: int
    m_sector1TimeMinutesPart: int
    m_sector2TimeMSPart: int
    m_sector2TimeMinutesPart: int
    m_deltaToCarInFrontMSPart: int
    m_deltaToCarInFrontMinutesPart: int
    m_deltaToRaceLeaderMSPart: int
    m_deltaToRaceLeaderMinutesPart: int
    m_lapDistance: float
    m_totalDistance: float
    m_safetyCarDelta: float
    m_carPosition: int
    m_currentLapNum: int
    m_pitStatus: int
    m_numPitStops: int
    m_sector: int
    m_currentLapInvalid: int
    m_penalties: int
    m_totalWarnings: int
    m_cornerCuttingWarnings: int
    m_numUnservedDriveThroughPens: int
    m_numUnservedStopGoPens: int
    m_gridPosition: int
    m_driverStatus: int
    m_resultStatus: int
    m_pitLaneTimerActive: int
    m_pitLaneTimeInLaneInMS: int
    m_pitStopTimerInMS: int
    m_pitStopShouldServePen: int
    m_speedTrapFastestSpeed: float
    m_speedTrapFastestLap: int


class CarTelemetryData(BaseModel):
    m_speed: int                      # km/h
    m_throttle: float                 # 0.0–1.0
    m_steer: float                    # -1.0–1.0
    m_brake: float                    # 0.0–1.0
    m_clutch: int                     # 0–100
    m_gear: int                       # 1–8, N=0, R=-1
    m_engineRPM: int
    m_drs: int
    m_revLightsPercent: int
    m_revLightsBitValue: int
    m_brakesTemperature: list[int]    # [4] °C
    m_tyresSurfaceTemperature: list[int]  # [4] °C
    m_tyresInnerTemperature: list[int]    # [4] °C
    m_engineTemperature: int          # °C
    m_tyresPressure: list[float]      # [4] psi
    m_surfaceType: list[int]          # [4]


class CarStatusData(BaseModel):
    m_tractionControl: int
    m_antiLockBrakes: int
    m_fuelMix: int
    m_frontBrakeBias: int
    m_pitLimiterStatus: int
    m_fuelInTank: float
    m_fuelCapacity: float
    m_fuelRemainingLaps: float
    m_maxRPM: int
    m_idleRPM: int
    m_maxGears: int
    m_drsAllowed: int
    m_drsActivationDistance: int
    m_actualTyreCompound: int
    m_visualTyreCompound: int
    m_tyresAgeLaps: int
    m_vehicleFIAFlags: int
    m_enginePowerICE: float
    m_enginePowerMGUK: float
    m_ersStoreEnergy: float
    m_ersDeployMode: int
    m_ersHarvestedThisLapMGUK: float
    m_ersHarvestedThisLapMGUH: float
    m_ersHarvestLimitPerLap: float
    m_ersDeployedThisLap: float
    m_networkPaused: int


class CarSetupData(BaseModel):
    m_frontWing: int
    m_rearWing: int
    m_onThrottle: int
    m_offThrottle: int
    m_frontCamber: float
    m_rearCamber: float
    m_frontToe: float
    m_rearToe: float
    m_frontSuspension: int
    m_rearSuspension: int
    m_frontAntiRollBar: int
    m_rearAntiRollBar: int
    m_frontSuspensionHeight: int
    m_rearSuspensionHeight: int
    m_brakePressure: int
    m_brakeBias: int
    m_engineBraking: int
    m_rearLeftTyrePressure: float
    m_rearRightTyrePressure: float
    m_frontLeftTyrePressure: float
    m_frontRightTyrePressure: float
    m_ballast: int
    m_fuelLoad: float


class CarDamageData(BaseModel):
    m_tyresWear: list[float]
    m_tyresDamage: list[int]
    m_brakesDamage: list[int]
    m_tyreBlisters: list[int]
    m_frontLeftWingDamage: int
    m_frontRightWingDamage: int
    m_rearWingDamage: int
    m_floorDamage: int
    m_diffuserDamage: int
    m_sidepodDamage: int
    m_drsFault: int
    m_ersFault: int
    m_gearBoxDamage: int
    m_engineDamage: int
    m_engineMGUHWear: int
    m_engineESWear: int
    m_engineCEWear: int
    m_engineICEWear: int
    m_engineMGUKWear: int
    m_engineTCWear: int
    m_engineBlown: int
    m_engineSeized: int


class ParticipantData(BaseModel):
    m_aiControlled: int
    m_driverId: int
    m_networkId: int
    m_teamId: int
    m_myTeam: int
    m_raceNumber: int
    m_nationality: int
    m_name: str
    m_yourTelemetry: int
    m_showOnlineNames: int
    m_techLevel: int
    m_platform: int
    m_numColours: int
    m_liveryColours: list[int]        # [12] = 4 色 × RGB


class LobbyInfoData(BaseModel):
    m_aiControlled: int
    m_teamId: int
    m_nationality: int
    m_platform: int
    m_name: str
    m_carNumber: int
    m_yourTelemetry: int
    m_showOnlineNames: int
    m_techLevel: int
    m_readyStatus: int


class FinalClassificationData(BaseModel):
    m_position: int
    m_numLaps: int
    m_gridPosition: int
    m_points: int
    m_numPitStops: int
    m_resultStatus: int
    m_resultReason: int
    m_bestLapTimeInMS: int
    m_totalRaceTime: float            # double（秒）
    m_penaltiesTime: int
    m_numPenalties: int
    m_numTyreStints: int
    m_tyreStintsActual: list[int]
    m_tyreStintsVisual: list[int]
    m_tyreStintsEndLaps: list[int]


class LapHistoryData(BaseModel):
    m_lapTimeInMS: int
    m_sector1TimeMSPart: int
    m_sector1TimeMinutesPart: int
    m_sector2TimeMSPart: int
    m_sector2TimeMinutesPart: int
    m_sector3TimeMSPart: int
    m_sector3TimeMinutesPart: int
    m_lapValidBitFlags: int


class TyreStintHistoryData(BaseModel):
    m_endLap: int
    m_tyreActualCompound: int
    m_tyreVisualCompound: int


class TyreSetData(BaseModel):
    m_actualTyreCompound: int
    m_visualTyreCompound: int
    m_wear: int
    m_available: int
    m_recommendedSession: int
    m_lifeSpan: int
    m_usableLife: int
    m_lapDeltaTime: int                # int16，ms
    m_fitted: int


class CarTelemetry2Data(BaseModel):
    m_activeAeroMode: int
    m_activeAeroAvailable: int
    m_activeAeroActivationDistance: int
    m_overtakeAvailable: int
    m_overtakeActive: int
    m_overtakeActivationDistance: int
    m_2026Regulations: int
    m_drivingWrongWay: int


class TimeTrialDataSet(BaseModel):
    m_carIdx: int
    m_teamId: int
    m_lapTimeInMS: int
    m_sector1TimeInMS: int
    m_sector2TimeInMS: int
    m_sector3TimeInMS: int
    m_tractionControl: int
    m_gearboxAssist: int
    m_antiLockBrakes: int
    m_equalCarPerformance: int
    m_customSetup: int
    m_valid: int


# ---------------------------------------------------------------------------
# 整包模型
# ---------------------------------------------------------------------------

class PacketMotionData(BaseModel):
    m_carMotionData: list[CarMotionData]


class PacketSessionData(BaseModel):
    m_weather: int
    m_trackTemperature: int
    m_airTemperature: int
    m_totalLaps: int
    m_trackLength: int
    m_sessionType: int
    m_trackId: int
    m_formula: int
    m_sessionTimeLeft: int
    m_sessionDuration: int
    m_pitSpeedLimit: int
    m_gamePaused: int
    m_isSpectating: int
    m_spectatorCarIndex: int
    m_sliProNativeSupport: int
    m_numMarshalZones: int
    m_marshalZones: list[MarshalZone]
    m_safetyCarStatus: int
    m_networkGame: int
    m_numWeatherForecastSamples: int
    m_weatherForecastSamples: list[WeatherForecastSample]
    m_forecastAccuracy: int
    m_aiDifficulty: int
    m_seasonLinkIdentifier: int
    m_weekendLinkIdentifier: int
    m_sessionLinkIdentifier: int
    m_pitStopWindowIdealLap: int
    m_pitStopWindowLatestLap: int
    m_pitStopRejoinPosition: int
    m_steeringAssist: int
    m_brakingAssist: int
    m_gearboxAssist: int
    m_pitAssist: int
    m_pitReleaseAssist: int
    m_ERSAssist: int
    m_DRSAssist: int
    m_dynamicRacingLine: int
    m_dynamicRacingLineType: int
    m_gameMode: int
    m_ruleSet: int
    m_timeOfDay: int
    m_sessionLength: int
    m_speedUnitsLeadPlayer: int
    m_temperatureUnitsLeadPlayer: int
    m_speedUnitsSecondaryPlayer: int
    m_temperatureUnitsSecondaryPlayer: int
    m_numSafetyCarPeriods: int
    m_numVirtualSafetyCarPeriods: int
    m_numRedFlagPeriods: int
    m_equalCarPerformance: int
    m_recoveryMode: int
    m_flashbackLimit: int
    m_surfaceType: int
    m_lowFuelMode: int
    m_raceStarts: int
    m_tyreTemperature: int
    m_pitLaneTyreSim: int
    m_carDamage: int
    m_carDamageRate: int
    m_collisions: int
    m_collisionsOffForFirstLapOnly: int
    m_mpUnsafePitRelease: int
    m_mpOffForGriefing: int
    m_cornerCuttingStringency: int
    m_parcFermeRules: int
    m_pitStopExperience: int
    m_safetyCar: int
    m_safetyCarExperience: int
    m_formationLap: int
    m_formationLapExperience: int
    m_redFlags: int
    m_affectsLicenceLevelSolo: int
    m_affectsLicenceLevelMP: int
    m_numSessionsInWeekend: int
    m_weekendStructure: list[int]
    m_sector2LapDistanceStart: float
    m_sector3LapDistanceStart: float
    m_activeAeroTrackStatus: int
    m_numActiveAeroZonesFull: int
    m_activeAeroZonesFull: list[ActiveAeroZone]
    m_numActiveAeroZonesPartial: int
    m_activeAeroZonesPartial: list[ActiveAeroZone]
    m_numDRSZones: int
    m_drsZones: list[DRSZone]
    m_startReactionTime: float
    m_antiLockBrakesAssist: int
    m_tractionControlAssist: int
    m_dynamicRacingLineHiVis: int
    m_dynamicRacingLineColourBlind: int
    m_recurringRewindPrompt: int


class PacketLapData(BaseModel):
    m_lapData: list[LapData]
    m_timeTrialPBCarIdx: int
    m_timeTrialRivalCarIdx: int


class PacketEventData(BaseModel):
    m_eventStringCode: str
    m_eventDetails: dict                # 按 code 解释后的字段；未知 code 为空 dict


class PacketParticipantsData(BaseModel):
    m_numActiveCars: int
    m_participants: list[ParticipantData]


class PacketCarSetupData(BaseModel):
    m_carSetupData: list[CarSetupData]
    m_nextFrontWingValue: float


class PacketCarTelemetryData(BaseModel):
    m_carTelemetryData: list[CarTelemetryData]
    m_mfdPanelIndex: int
    m_mfdPanelIndexSecondaryPlayer: int
    m_suggestedGear: int


class PacketCarStatusData(BaseModel):
    m_carStatusData: list[CarStatusData]


class PacketFinalClassificationData(BaseModel):
    m_numCars: int
    m_classificationData: list[FinalClassificationData]


class PacketLobbyInfoData(BaseModel):
    m_numPlayers: int
    m_lobbyPlayers: list[LobbyInfoData]


class PacketCarDamageData(BaseModel):
    m_carDamageData: list[CarDamageData]


class PacketSessionHistoryData(BaseModel):
    m_carIdx: int
    m_numLaps: int
    m_numTyreStints: int
    m_bestLapTimeLapNum: int
    m_bestSector1LapNum: int
    m_bestSector2LapNum: int
    m_bestSector3LapNum: int
    m_lapHistoryData: list[LapHistoryData]
    m_tyreStintsHistoryData: list[TyreStintHistoryData]


class PacketTyreSetsData(BaseModel):
    m_carIdx: int
    m_tyreSetData: list[TyreSetData]
    m_fittedIdx: int


class PacketMotionExData(BaseModel):
    m_suspensionPosition: list[float]
    m_suspensionVelocity: list[float]
    m_suspensionAcceleration: list[float]
    m_wheelSpeed: list[float]
    m_wheelSlipRatio: list[float]
    m_wheelSlipAngle: list[float]
    m_wheelLatForce: list[float]
    m_wheelLongForce: list[float]
    m_heightOfCOGAboveGround: float
    m_localVelocityX: float
    m_localVelocityY: float
    m_localVelocityZ: float
    m_angularVelocityX: float
    m_angularVelocityY: float
    m_angularVelocityZ: float
    m_angularAccelerationX: float
    m_angularAccelerationY: float
    m_angularAccelerationZ: float
    m_frontWheelsAngle: float
    m_wheelVertForce: list[float]
    m_frontAeroHeight: float
    m_rearAeroHeight: float
    m_frontRollAngle: float
    m_rearRollAngle: float
    m_chassisYaw: float
    m_chassisPitch: float
    m_wheelCamber: list[float]
    m_wheelCamberGain: list[float]


class PacketTimeTrialData(BaseModel):
    m_playerSessionBestDataSet: TimeTrialDataSet
    m_personalBestDataSet: TimeTrialDataSet
    m_rivalDataSet: TimeTrialDataSet


class PacketLapPositionsData(BaseModel):
    m_numLaps: int
    m_lapStart: int
    m_positionForVehicleIdx: list[list[int]]   # [50][24]


class PacketCarTelemetry2Data(BaseModel):
    m_carTelemetry2Data: list[CarTelemetry2Data]


# ---------------------------------------------------------------------------
# 数组字段规格：字段名 → 元素数（struct 格式串里 "4H"/"12B" 等展开成多个标量，
# 需重新聚合成 list）。标量字段无需登记。
# ---------------------------------------------------------------------------

_CAR_TELEMETRY_ARRAYS = {
    "m_brakesTemperature": 4,
    "m_tyresSurfaceTemperature": 4,
    "m_tyresInnerTemperature": 4,
    "m_tyresPressure": 4,
    "m_surfaceType": 4,
}
_CAR_DAMAGE_ARRAYS = {
    "m_tyresWear": 4,
    "m_tyresDamage": 4,
    "m_brakesDamage": 4,
    "m_tyreBlisters": 4,
}
_PARTICIPANT_ARRAYS = {"m_liveryColours": 12}
_FINAL_CLASSIFICATION_ARRAYS = {
    "m_tyreStintsActual": 8,
    "m_tyreStintsVisual": 8,
    "m_tyreStintsEndLaps": 8,
}


# ---------------------------------------------------------------------------
# 解析函数
# ---------------------------------------------------------------------------

def _parse_motion(data: bytes) -> PacketMotionData:
    cars = _build_array(CarMotionData, CAR_MOTION_FMT, data, HEADER_SIZE, MAX_CARS)
    return PacketMotionData(m_carMotionData=cars)


def _parse_session(data: bytes) -> PacketSessionData:
    off = HEADER_SIZE
    lead_fmt = "BbbBHBbBHH" + "B" * 6
    (weather, track_temp, air_temp, total_laps, track_length, session_type, track_id,
     formula, time_left, duration, pit_speed, paused, spectating, spectator_idx, sli,
     num_marshal) = struct.unpack_from("<" + lead_fmt, data, off)
    off += _size_of("<" + lead_fmt)

    marshals = _build_array(MarshalZone, MARSHAL_ZONE_FMT, data, off, MAX_MARSHAL_ZONES)
    off += MAX_MARSHAL_ZONES * _size_of(MARSHAL_ZONE_FMT)

    (safety_car_status, network_game, num_weather) = struct.unpack_from("<BBB", data, off)
    off += 3

    weather_samples = _build_array(WeatherForecastSample, WEATHER_FORECAST_FMT, data, off, MAX_WEATHER_FORECAST)
    off += MAX_WEATHER_FORECAST * _size_of(WEATHER_FORECAST_FMT)

    tail1_fmt = "BB" + "III" + "B" * 14 + "I" + "B" * 33 + "B" * MAX_SESSIONS_IN_WEEKEND
    tail1 = struct.unpack_from("<" + tail1_fmt, data, off)
    off += _size_of("<" + tail1_fmt)
    (forecast_accuracy, ai_difficulty, season_link, weekend_link, session_link) = tail1[0:5]
    (pit_window_ideal, pit_window_latest, pit_rejoin, steering_assist, braking_assist,
     gearbox_assist, pit_assist, pit_release_assist, ers_assist, drs_assist,
     dynamic_line, dynamic_line_type, game_mode, rule_set) = tail1[5:19]
    time_of_day = tail1[19]
    rest = tail1[20:20 + 33]
    weekend_structure = list(tail1[20 + 33:])
    (session_length, speed_lead, temp_lead, speed_secondary, temp_secondary,
     num_safety_car, num_vsc, num_red_flag, equal_perf, recovery_mode,
     flashback_limit, surface_type, low_fuel, race_starts, tyre_temp,
     pit_lane_tyre_sim, car_damage, car_damage_rate, collisions, collisions_first_lap,
     mp_unsafe_pit, mp_off_griefing, corner_cutting, parc_ferme, pit_experience,
     safety_car, safety_car_experience, formation_lap, formation_lap_experience,
     red_flags, affects_licence_solo, affects_licence_mp, num_sessions_weekend) = rest

    (sector2_start, sector3_start) = struct.unpack_from("<ff", data, off)
    off += 8

    (active_aero_status, num_aero_full) = struct.unpack_from("<BB", data, off)
    off += 2
    aero_full = _build_array(ActiveAeroZone, ACTIVE_AERO_ZONE_FMT, data, off, MAX_ACTIVE_AERO_ZONES)
    off += MAX_ACTIVE_AERO_ZONES * _size_of(ACTIVE_AERO_ZONE_FMT)

    (num_aero_partial,) = struct.unpack_from("<B", data, off)
    off += 1
    aero_partial = _build_array(ActiveAeroZone, ACTIVE_AERO_ZONE_FMT, data, off, MAX_ACTIVE_AERO_ZONES)
    off += MAX_ACTIVE_AERO_ZONES * _size_of(ACTIVE_AERO_ZONE_FMT)

    (num_drs,) = struct.unpack_from("<B", data, off)
    off += 1
    drs_zones = _build_array(DRSZone, DRS_ZONE_FMT, data, off, MAX_DRS_ZONES)
    off += MAX_DRS_ZONES * _size_of(DRS_ZONE_FMT)

    (start_reaction, anti_lock, traction, drl_hivis, drl_colourblind, recurring_rewind) = \
        struct.unpack_from("<fBBBBB", data, off)

    return PacketSessionData(
        m_weather=weather, m_trackTemperature=track_temp, m_airTemperature=air_temp,
        m_totalLaps=total_laps, m_trackLength=track_length, m_sessionType=session_type,
        m_trackId=track_id, m_formula=formula, m_sessionTimeLeft=time_left,
        m_sessionDuration=duration, m_pitSpeedLimit=pit_speed, m_gamePaused=paused,
        m_isSpectating=spectating, m_spectatorCarIndex=spectator_idx,
        m_sliProNativeSupport=sli, m_numMarshalZones=num_marshal, m_marshalZones=marshals,
        m_safetyCarStatus=safety_car_status, m_networkGame=network_game,
        m_numWeatherForecastSamples=num_weather, m_weatherForecastSamples=weather_samples,
        m_forecastAccuracy=forecast_accuracy, m_aiDifficulty=ai_difficulty,
        m_seasonLinkIdentifier=season_link, m_weekendLinkIdentifier=weekend_link,
        m_sessionLinkIdentifier=session_link, m_pitStopWindowIdealLap=pit_window_ideal,
        m_pitStopWindowLatestLap=pit_window_latest, m_pitStopRejoinPosition=pit_rejoin,
        m_steeringAssist=steering_assist, m_brakingAssist=braking_assist,
        m_gearboxAssist=gearbox_assist, m_pitAssist=pit_assist,
        m_pitReleaseAssist=pit_release_assist, m_ERSAssist=ers_assist, m_DRSAssist=drs_assist,
        m_dynamicRacingLine=dynamic_line, m_dynamicRacingLineType=dynamic_line_type,
        m_gameMode=game_mode, m_ruleSet=rule_set, m_timeOfDay=time_of_day,
        m_sessionLength=session_length, m_speedUnitsLeadPlayer=speed_lead,
        m_temperatureUnitsLeadPlayer=temp_lead, m_speedUnitsSecondaryPlayer=speed_secondary,
        m_temperatureUnitsSecondaryPlayer=temp_secondary, m_numSafetyCarPeriods=num_safety_car,
        m_numVirtualSafetyCarPeriods=num_vsc, m_numRedFlagPeriods=num_red_flag,
        m_equalCarPerformance=equal_perf, m_recoveryMode=recovery_mode,
        m_flashbackLimit=flashback_limit, m_surfaceType=surface_type, m_lowFuelMode=low_fuel,
        m_raceStarts=race_starts, m_tyreTemperature=tyre_temp, m_pitLaneTyreSim=pit_lane_tyre_sim,
        m_carDamage=car_damage, m_carDamageRate=car_damage_rate, m_collisions=collisions,
        m_collisionsOffForFirstLapOnly=collisions_first_lap, m_mpUnsafePitRelease=mp_unsafe_pit,
        m_mpOffForGriefing=mp_off_griefing, m_cornerCuttingStringency=corner_cutting,
        m_parcFermeRules=parc_ferme, m_pitStopExperience=pit_experience, m_safetyCar=safety_car,
        m_safetyCarExperience=safety_car_experience, m_formationLap=formation_lap,
        m_formationLapExperience=formation_lap_experience, m_redFlags=red_flags,
        m_affectsLicenceLevelSolo=affects_licence_solo, m_affectsLicenceLevelMP=affects_licence_mp,
        m_numSessionsInWeekend=num_sessions_weekend, m_weekendStructure=weekend_structure,
        m_sector2LapDistanceStart=sector2_start, m_sector3LapDistanceStart=sector3_start,
        m_activeAeroTrackStatus=active_aero_status, m_numActiveAeroZonesFull=num_aero_full,
        m_activeAeroZonesFull=aero_full, m_numActiveAeroZonesPartial=num_aero_partial,
        m_activeAeroZonesPartial=aero_partial, m_numDRSZones=num_drs, m_drsZones=drs_zones,
        m_startReactionTime=start_reaction, m_antiLockBrakesAssist=anti_lock,
        m_tractionControlAssist=traction, m_dynamicRacingLineHiVis=drl_hivis,
        m_dynamicRacingLineColourBlind=drl_colourblind, m_recurringRewindPrompt=recurring_rewind,
    )


def _parse_lap(data: bytes) -> PacketLapData:
    cars = _build_array(LapData, LAP_DATA_FMT, data, HEADER_SIZE, MAX_CARS)
    off = HEADER_SIZE + MAX_CARS * _size_of(LAP_DATA_FMT)
    (pb_idx, rival_idx) = struct.unpack_from("<BB", data, off)
    return PacketLapData(m_lapData=cars, m_timeTrialPBCarIdx=pb_idx, m_timeTrialRivalCarIdx=rival_idx)


_EVENT_DETAIL_FORMATS: dict[str, tuple[str, tuple[str, ...]]] = {
    "FTLP": ("Bf", ("vehicleIdx", "lapTime")),
    "RTMT": ("BB", ("vehicleIdx", "reason")),
    "DRSD": ("B", ("reason",)),
    "TMPT": ("B", ("vehicleIdx",)),
    "RCWN": ("B", ("vehicleIdx",)),
    "PENA": ("BBBBBBB", ("penaltyType", "infringementType", "vehicleIdx", "otherVehicleIdx",
                          "time", "lapNum", "placesGained")),
    "SPTP": ("BfBBf", ("vehicleIdx", "speed", "isOverallFastestInSession",
                        "isDriverFastestInSession", "fastestSpeedInSession")),
    "STLG": ("B", ("numLights",)),
    "DTSV": ("B", ("vehicleIdx",)),
    "SGSV": ("Bf", ("vehicleIdx", "stopTime")),
    "FLBK": ("If", ("flashbackFrameIdentifier", "flashbackSessionTime")),
    "BUTN": ("I", ("buttonStatus",)),
    "OVTK": ("BB", ("overtakingVehicleIdx", "beingOvertakenVehicleIdx")),
    "SCAR": ("BB", ("safetyCarType", "eventType")),
    "COLL": ("BBB", ("vehicle1Idx", "vehicle2Idx", "severity")),
}


def _parse_event(data: bytes) -> PacketEventData:
    code_raw, details_raw = struct.unpack_from("<4s12s", data, HEADER_SIZE)
    code = code_raw.decode("ascii", errors="replace")
    details: dict = {}
    spec = _EVENT_DETAIL_FORMATS.get(code)
    if spec is not None:
        fmt, names = spec
        values = struct.unpack_from("<" + fmt, details_raw, 0)
        details = dict(zip(names, values))
    return PacketEventData(m_eventStringCode=code, m_eventDetails=details)


def _parse_participants(data: bytes) -> PacketParticipantsData:
    off = HEADER_SIZE
    (num_active,) = struct.unpack_from("<B", data, off)
    off += 1
    size = _size_of(PARTICIPANT_FMT)
    cars = []
    for i in range(MAX_CARS):
        values = struct.unpack_from("<" + PARTICIPANT_FMT, data, off + i * size)
        vals = list(values)
        vals[7] = _decode_name(vals[7])          # name 字段（index 7，32s → str）
        cars.append(_from_values(ParticipantData, tuple(vals), _PARTICIPANT_ARRAYS))
    return PacketParticipantsData(m_numActiveCars=num_active, m_participants=cars)


def _parse_car_setups(data: bytes) -> PacketCarSetupData:
    cars = _build_array(CarSetupData, CAR_SETUP_FMT, data, HEADER_SIZE, MAX_CARS)
    off = HEADER_SIZE + MAX_CARS * _size_of(CAR_SETUP_FMT)
    (next_front_wing,) = struct.unpack_from("<f", data, off)
    return PacketCarSetupData(m_carSetupData=cars, m_nextFrontWingValue=next_front_wing)


def _parse_car_telemetry(data: bytes) -> PacketCarTelemetryData:
    cars = _build_array(CarTelemetryData, CAR_TELEMETRY_FMT, data, HEADER_SIZE, MAX_CARS, _CAR_TELEMETRY_ARRAYS)
    off = HEADER_SIZE + MAX_CARS * _size_of(CAR_TELEMETRY_FMT)
    (mfd, mfd_secondary, suggested_gear) = struct.unpack_from("<BBb", data, off)
    return PacketCarTelemetryData(
        m_carTelemetryData=cars, m_mfdPanelIndex=mfd,
        m_mfdPanelIndexSecondaryPlayer=mfd_secondary, m_suggestedGear=suggested_gear,
    )


def _parse_car_status(data: bytes) -> PacketCarStatusData:
    cars = _build_array(CarStatusData, CAR_STATUS_FMT, data, HEADER_SIZE, MAX_CARS)
    return PacketCarStatusData(m_carStatusData=cars)


def _parse_final_classification(data: bytes) -> PacketFinalClassificationData:
    off = HEADER_SIZE
    (num_cars,) = struct.unpack_from("<B", data, off)
    off += 1
    cars = _build_array(FinalClassificationData, FINAL_CLASSIFICATION_FMT, data, off, MAX_CARS, _FINAL_CLASSIFICATION_ARRAYS)
    return PacketFinalClassificationData(m_numCars=num_cars, m_classificationData=cars)


def _parse_lobby_info(data: bytes) -> PacketLobbyInfoData:
    off = HEADER_SIZE
    (num_players,) = struct.unpack_from("<B", data, off)
    off += 1
    size = _size_of(LOBBY_INFO_FMT)
    players = []
    for i in range(MAX_CARS):
        values = struct.unpack_from("<" + LOBBY_INFO_FMT, data, off + i * size)
        vals = list(values)
        vals[4] = _decode_name(vals[4])          # name 字段（index 4）
        players.append(_from_values(LobbyInfoData, tuple(vals), {}))
    return PacketLobbyInfoData(m_numPlayers=num_players, m_lobbyPlayers=players)


def _parse_car_damage(data: bytes) -> PacketCarDamageData:
    cars = _build_array(CarDamageData, CAR_DAMAGE_FMT, data, HEADER_SIZE, MAX_CARS, _CAR_DAMAGE_ARRAYS)
    return PacketCarDamageData(m_carDamageData=cars)


def _parse_session_history(data: bytes) -> PacketSessionHistoryData:
    off = HEADER_SIZE
    (car_idx, num_laps, num_stints, best_lap, best_s1, best_s2, best_s3) = \
        struct.unpack_from("<BBBBBBB", data, off)
    off += 7
    laps = _build_array(LapHistoryData, LAP_HISTORY_FMT, data, off, MAX_LAP_HISTORY)
    off += MAX_LAP_HISTORY * _size_of(LAP_HISTORY_FMT)
    stints = _build_array(TyreStintHistoryData, TYRE_STINT_HISTORY_FMT, data, off, MAX_TYRE_STINTS)
    return PacketSessionHistoryData(
        m_carIdx=car_idx, m_numLaps=num_laps, m_numTyreStints=num_stints,
        m_bestLapTimeLapNum=best_lap, m_bestSector1LapNum=best_s1,
        m_bestSector2LapNum=best_s2, m_bestSector3LapNum=best_s3,
        m_lapHistoryData=laps, m_tyreStintsHistoryData=stints,
    )


def _parse_tyre_sets(data: bytes) -> PacketTyreSetsData:
    off = HEADER_SIZE
    (car_idx,) = struct.unpack_from("<B", data, off)
    off += 1
    sets = _build_array(TyreSetData, TYRE_SET_FMT, data, off, MAX_TYRE_SETS)
    off += MAX_TYRE_SETS * _size_of(TYRE_SET_FMT)
    (fitted_idx,) = struct.unpack_from("<B", data, off)
    return PacketTyreSetsData(m_carIdx=car_idx, m_tyreSetData=sets, m_fittedIdx=fitted_idx)


def _parse_motion_ex(data: bytes) -> PacketMotionExData:
    values = struct.unpack_from("<" + "f" * 61, data, HEADER_SIZE)
    names = (
        "m_suspensionPosition", "m_suspensionVelocity", "m_suspensionAcceleration",
        "m_wheelSpeed", "m_wheelSlipRatio", "m_wheelSlipAngle", "m_wheelLatForce",
        "m_wheelLongForce",
    )
    # 前 8 组各 4 个 float
    groups: dict[str, list[float]] = {}
    idx = 0
    for name in names:
        groups[name] = list(values[idx:idx + 4])
        idx += 4
    scalars = values[idx:]
    return PacketMotionExData(
        **groups,
        m_heightOfCOGAboveGround=scalars[0],
        m_localVelocityX=scalars[1], m_localVelocityY=scalars[2], m_localVelocityZ=scalars[3],
        m_angularVelocityX=scalars[4], m_angularVelocityY=scalars[5], m_angularVelocityZ=scalars[6],
        m_angularAccelerationX=scalars[7], m_angularAccelerationY=scalars[8],
        m_angularAccelerationZ=scalars[9], m_frontWheelsAngle=scalars[10],
        m_wheelVertForce=list(scalars[11:15]),
        m_frontAeroHeight=scalars[15], m_rearAeroHeight=scalars[16],
        m_frontRollAngle=scalars[17], m_rearRollAngle=scalars[18],
        m_chassisYaw=scalars[19], m_chassisPitch=scalars[20],
        m_wheelCamber=list(scalars[21:25]), m_wheelCamberGain=list(scalars[25:29]),
    )


def _parse_time_trial(data: bytes) -> PacketTimeTrialData:
    off = HEADER_SIZE
    size = _size_of(TIME_TRIAL_SET_FMT)
    sets = []
    for i in range(3):
        values = struct.unpack_from("<" + TIME_TRIAL_SET_FMT, data, off + i * size)
        sets.append(TimeTrialDataSet(**dict(zip(_fields(TimeTrialDataSet), values))))
    return PacketTimeTrialData(
        m_playerSessionBestDataSet=sets[0], m_personalBestDataSet=sets[1], m_rivalDataSet=sets[2],
    )


def _parse_lap_positions(data: bytes) -> PacketLapPositionsData:
    off = HEADER_SIZE
    (num_laps, lap_start) = struct.unpack_from("<BB", data, off)
    off += 2
    rows = []
    for _ in range(MAX_LAP_POSITIONS_LAPS):
        row = list(struct.unpack_from("<" + "B" * MAX_CARS, data, off))
        off += MAX_CARS
        rows.append(row)
    return PacketLapPositionsData(m_numLaps=num_laps, m_lapStart=lap_start, m_positionForVehicleIdx=rows)


def _parse_car_telemetry2(data: bytes) -> PacketCarTelemetry2Data:
    cars = _build_array(CarTelemetry2Data, CAR_TELEMETRY2_FMT, data, HEADER_SIZE, MAX_CARS)
    return PacketCarTelemetry2Data(m_carTelemetry2Data=cars)


_PARSERS = {
    0: _parse_motion,
    1: _parse_session,
    2: _parse_lap,
    3: _parse_event,
    4: _parse_participants,
    5: _parse_car_setups,
    6: _parse_car_telemetry,
    7: _parse_car_status,
    8: _parse_final_classification,
    9: _parse_lobby_info,
    10: _parse_car_damage,
    11: _parse_session_history,
    12: _parse_tyre_sets,
    13: _parse_motion_ex,
    14: _parse_time_trial,
    15: _parse_lap_positions,
    16: _parse_car_telemetry2,
}


def parse_payload(packet_id: int, data: bytes) -> Optional[BaseModel]:
    """按 packetId 解析 payload（data 含 29 字节 header）。

    返回类型化模型；未知 packetId / payload 过短 / 解析异常 → None。
    """
    parser = _PARSERS.get(packet_id)
    fmt = PACKET_PAYLOAD_FMT.get(packet_id)
    if parser is None or fmt is None:
        return None
    if len(data) < HEADER_SIZE + _size_of(fmt):
        return None
    try:
        return parser(data)
    except (struct.error, ValueError, IndexError):
        return None
