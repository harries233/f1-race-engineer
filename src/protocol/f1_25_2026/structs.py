"""F1_25_2026 payload 结构体布局（官方 Spec 逐字段转录）。

数据源（最高优先级，已 VERIFIED）：
  「2026 Season Pack Telemetry Output Structures (1).txt」—— 920 行 C++ 结构体。
  明文：Little Endian、packed 无 padding。

本文件只做「C++ 结构体 → struct 格式串」的机械转录，不含业务逻辑。
每个格式串都用 `struct.calcsize` 在 import 期断言等于官方 registry 的
expected_size - HEADER_SIZE（payload 长度），像 header.py 一样编译期锁死偏移错误。

格式串约定：
  - 本文件的格式串都不带 "<" 前缀，只描述字段序列；只有顶层整包格式串
    （PACKET_PAYLOAD_FMT 表）以 "<" 开头。
  - 子结构体可重复 N 次时，用字符串乘法展开（如 CAR_MOTION_FMT * MAX_CARS）。
  - 类型映射：uint8=B, int8=b, uint16=H, int16=h, uint32=I, float=f, double=d,
    char[N]=Ns。
"""

from __future__ import annotations

import struct

from protocol.f1_25_2026.header import HEADER_SIZE

# ---------------------------------------------------------------------------
# 数组尺寸常量（官方 Spec 顶部 static const）
# ---------------------------------------------------------------------------

MAX_CARS = 24                    # cs_maxNumCarsInUDPData
MAX_PARTICIPANT_NAME_LEN = 32    # cs_maxParticipantNameLen
MAX_TYRE_STINTS = 8              # cs_maxTyreStints
MAX_TYRE_SETS = 20               # cs_maxNumTyreSets = 13 slick + 7 wet
MAX_MARSHAL_ZONES = 21           # cs_maxMarshalZonesPerLap
MAX_ACTIVE_AERO_ZONES = 8        # cs_maxActiveAeroZonesPerLap
MAX_DRS_ZONES = 4                # cs_maxDRSZonesPerLap
MAX_WEATHER_FORECAST = 64        # cs_maxWeatherForecastSamples
MAX_SESSIONS_IN_WEEKEND = 12     # cs_maxSessionsInWeekend
MAX_LAP_HISTORY = 100            # cs_maxNumLapsInHistory
MAX_LAP_POSITIONS_LAPS = 50      # cs_maxNumLapsInLapPositionsHistoryPacket
EVENT_STRING_CODE_LEN = 4        # cs_eventStringCodeLen

# ---------------------------------------------------------------------------
# 子结构体格式串（不带 "<"）
# ---------------------------------------------------------------------------

# Session 内嵌区段
MARSHAL_ZONE_FMT = "fb"              # MarshalZone: float zoneStart + int8 zoneFlag (5B)
ACTIVE_AERO_ZONE_FMT = "ff"          # ActiveAeroZone: float start + float end (8B)
DRS_ZONE_FMT = "ff"                  # DRSZone: float start + float end (8B)
WEATHER_FORECAST_FMT = "BBBbbbbB"    # WeatherForecastSample (8B)

# Motion（per car）
CAR_MOTION_FMT = "3f3f3h3h3h3f"      # 54B：位置3f 速度3f 前向3h 右向3h G力3h 姿态3f

# Lap Data（per car，57B）
LAP_DATA_FMT = (
    "II"                                # lastLapTimeInMS, currentLapTimeInMS
    + "HBHBHBHB"                        # sector1/2 (ms+min), deltaInFront (ms+min), deltaLeader (ms+min)
    + "fff"                             # lapDistance, totalDistance, safetyCarDelta
    + "B" * 15                          # carPosition..pitLaneTimerActive（15 个 uint8）
    + "HHB"                             # pitLaneTimeInLaneInMS, pitStopTimerInMS, pitStopShouldServePen
    + "fB"                              # speedTrapFastestSpeed, speedTrapFastestLap
)

# Car Telemetry（per car，59B）
CAR_TELEMETRY_FMT = (
    "Hfff"                              # speed, throttle, steer, brake
    + "Bb"                              # clutch, gear
    + "HBBH"                            # engineRPM, drs, revLightsPercent, revLightsBitValue
    + "4H4B4B"                          # brakesTemperature[4], tyresSurfaceTemperature[4], tyresInnerTemperature[4]
    + "B"                               # engineTemperature
    + "4f4B"                            # tyresPressure[4], surfaceType[4]
)

# Car Status（per car，59B）
CAR_STATUS_FMT = (
    "BBBBB"                             # tractionControl, antiLockBrakes, fuelMix, frontBrakeBias, pitLimiterStatus
    + "fff"                             # fuelInTank, fuelCapacity, fuelRemainingLaps
    + "HH"                              # maxRPM, idleRPM
    + "BBH"                             # maxGears, drsAllowed, drsActivationDistance
    + "BBB"                             # actualTyreCompound, visualTyreCompound, tyresAgeLaps
    + "b"                               # vehicleFIAFlags
    + "fff"                             # enginePowerICE, enginePowerMGUK, ersStoreEnergy
    + "B"                               # ersDeployMode
    + "ffff"                            # ersHarvestedThisLapMGUK/MGUH, ersHarvestLimitPerLap, ersDeployedThisLap
    + "B"                               # networkPaused
)

# Car Setups（per car，50B）
CAR_SETUP_FMT = (
    "BBBB"                              # frontWing, rearWing, onThrottle, offThrottle
    + "ffff"                            # frontCamber, rearCamber, frontToe, rearToe
    + "B" * 9                           # front/rearSuspension, front/rearAntiRollBar, front/rearHeight,
                                        # brakePressure, brakeBias, engineBraking
    + "ffff"                            # rearLeft/rearRight/frontLeft/frontRightTyrePressure
    + "B"                               # ballast
    + "f"                               # fuelLoad
)

# Car Damage（per car，46B）
CAR_DAMAGE_FMT = (
    "4f"                                # tyresWear[4]
    + "4B"                              # tyresDamage[4]
    + "4B"                              # brakesDamage[4]
    + "4B"                              # tyreBlisters[4]
    + "B" * 18                          # 18 个 uint8 损伤字段（翼面/地板/扩散器/侧箱/引擎件/DRS/ERS fault…）
)

# Participants（per car，60B）
PARTICIPANT_FMT = (
    "BHHH"                              # aiControlled, driverId, networkId, teamId
    + "BBB"                             # myTeam, raceNumber, nationality
    + "32s"                             # name[32]
    + "BB"                              # yourTelemetry, showOnlineNames
    + "H"                               # techLevel
    + "BB"                              # platform, numColours
    + "12B"                             # liveryColours[4]（每色 3×uint8）
)

# Lobby Info（per player，43B）
LOBBY_INFO_FMT = (
    "BHBB"                              # aiControlled, teamId, nationality, platform
    + "32s"                             # name[32]
    + "BBB"                             # carNumber, yourTelemetry, showOnlineNames
    + "H"                               # techLevel
    + "B"                               # readyStatus
)

# Final Classification（per car，46B）
FINAL_CLASSIFICATION_FMT = (
    "BBBBBBB"                           # position, numLaps, gridPosition, points, numPitStops,
                                        # resultStatus, resultReason
    + "I"                               # bestLapTimeInMS
    + "d"                               # totalRaceTime（double，唯一一个 double）
    + "BBB"                             # penaltiesTime, numPenalties, numTyreStints
    + "8B8B8B"                          # tyreStintsActual[8], tyreStintsVisual[8], tyreStintsEndLaps[8]
)

# Session History 内嵌
LAP_HISTORY_FMT = "IHBHBHBB"            # LapHistoryData（14B）：lapTime, sector1/2/3(ms+min), lapValidBitFlags
TYRE_STINT_HISTORY_FMT = "BBB"          # TyreStintHistoryData（3B）

# Tyre Sets（per set，10B）
TYRE_SET_FMT = (
    "BBBBBBB"                           # actualTyreCompound, visualTyreCompound, wear, available,
                                        # recommendedSession, lifeSpan, usableLife
    + "h"                               # lapDeltaTime（int16）
    + "B"                               # fitted
)

# Car Telemetry 2（per car，10B）
CAR_TELEMETRY2_FMT = (
    "BBH"                               # activeAeroMode, activeAeroAvailable, activeAeroActivationDistance
    + "BBH"                             # overtakeAvailable, overtakeActive, overtakeActivationDistance
    + "BB"                              # 2026Regulations, drivingWrongWay
)

# Time Trial（per set，25B）
TIME_TRIAL_SET_FMT = (
    "BH"                                # carIdx, teamId
    + "IIII"                            # lapTimeInMS, sector1/2/3TimeInMS
    + "BBBBBB"                          # tractionControl, gearboxAssist, antiLockBrakes,
                                        # equalCarPerformance, customSetup, valid
)

# ---------------------------------------------------------------------------
# 整包 payload 格式串（含 "<"；不含 29 字节 header）
# ---------------------------------------------------------------------------

MOTION_PAYLOAD_FMT = "<" + CAR_MOTION_FMT * MAX_CARS

SESSION_PAYLOAD_FMT = "<" + (
    "BbbBHBbBHH"                        # weather..numMarshalZones（19B）
    + "B" * 6
    + MARSHAL_ZONE_FMT * MAX_MARSHAL_ZONES                 # 21 × 5B
    + "BBB"                             # safetyCarStatus, networkGame, numWeatherForecastSamples
    + WEATHER_FORECAST_FMT * MAX_WEATHER_FORECAST          # 64 × 8B
    + "BB" + "III" + "B" * 14           # forecastAccuracy..ruleSet
    + "I" + "B" * 33 + "B" * MAX_SESSIONS_IN_WEEKEND      # timeOfDay..weekendStructure[12]
    + "ff"                              # sector2LapDistanceStart, sector3LapDistanceStart
    + "BB" + ACTIVE_AERO_ZONE_FMT * MAX_ACTIVE_AERO_ZONES  # activeAeroTrackStatus + zonesFull[8]
    + "B" + ACTIVE_AERO_ZONE_FMT * MAX_ACTIVE_AERO_ZONES   # numActiveAeroZonesPartial + zonesPartial[8]
    + "B" + DRS_ZONE_FMT * MAX_DRS_ZONES                    # numDRSZones + drsZones[4]
    + "f"                               # startReactionTime
    + "BBBBB"                           # antiLockBrakes/tractionControl/drlHiVis/drlColourBlind/recurringRewind
)

LAP_PAYLOAD_FMT = "<" + LAP_DATA_FMT * MAX_CARS + "BB"   # + timeTrialPBCarIdx, timeTrialRivalCarIdx

EVENT_PAYLOAD_FMT = "<" + "4s" + "12s"                   # eventStringCode + EventDataDetails union（12B）

PARTICIPANTS_PAYLOAD_FMT = "<" + "B" + PARTICIPANT_FMT * MAX_CARS  # numActiveCars + 24 车

CAR_SETUPS_PAYLOAD_FMT = "<" + CAR_SETUP_FMT * MAX_CARS + "f"      # + nextFrontWingValue

CAR_TELEMETRY_PAYLOAD_FMT = "<" + CAR_TELEMETRY_FMT * MAX_CARS + "BBb"  # + mfd 两字段 + suggestedGear

CAR_STATUS_PAYLOAD_FMT = "<" + CAR_STATUS_FMT * MAX_CARS

FINAL_CLASSIFICATION_PAYLOAD_FMT = "<" + "B" + FINAL_CLASSIFICATION_FMT * MAX_CARS  # numCars + 24 车

LOBBY_INFO_PAYLOAD_FMT = "<" + "B" + LOBBY_INFO_FMT * MAX_CARS                      # numPlayers + 24 人

CAR_DAMAGE_PAYLOAD_FMT = "<" + CAR_DAMAGE_FMT * MAX_CARS

SESSION_HISTORY_PAYLOAD_FMT = "<" + (
    "B" * 7                             # carIdx, numLaps, numTyreStints, best 4 lap nums
    + LAP_HISTORY_FMT * MAX_LAP_HISTORY              # 100 圈
    + TYRE_STINT_HISTORY_FMT * MAX_TYRE_STINTS        # 8 段
)

TYRE_SETS_PAYLOAD_FMT = "<" + "B" + TYRE_SET_FMT * MAX_TYRE_SETS + "B"  # carIdx + 20 套 + fittedIdx

MOTION_EX_PAYLOAD_FMT = "<" + "f" * 61           # 全 float 单体结构

TIME_TRIAL_PAYLOAD_FMT = "<" + TIME_TRIAL_SET_FMT * 3  # 3 组（session best / personal best / rival）

LAP_POSITIONS_PAYLOAD_FMT = "<" + "BB" + "B" * (MAX_LAP_POSITIONS_LAPS * MAX_CARS)  # numLaps + lapStart + 50×24

CAR_TELEMETRY2_PAYLOAD_FMT = "<" + CAR_TELEMETRY2_FMT * MAX_CARS


# ---------------------------------------------------------------------------
# packetId → 整包 payload 格式串（与官方 registry 一一对应）
# ---------------------------------------------------------------------------

PACKET_PAYLOAD_FMT: dict[int, str] = {
    0: MOTION_PAYLOAD_FMT,
    1: SESSION_PAYLOAD_FMT,
    2: LAP_PAYLOAD_FMT,
    3: EVENT_PAYLOAD_FMT,
    4: PARTICIPANTS_PAYLOAD_FMT,
    5: CAR_SETUPS_PAYLOAD_FMT,
    6: CAR_TELEMETRY_PAYLOAD_FMT,
    7: CAR_STATUS_PAYLOAD_FMT,
    8: FINAL_CLASSIFICATION_PAYLOAD_FMT,
    9: LOBBY_INFO_PAYLOAD_FMT,
    10: CAR_DAMAGE_PAYLOAD_FMT,
    11: SESSION_HISTORY_PAYLOAD_FMT,
    12: TYRE_SETS_PAYLOAD_FMT,
    13: MOTION_EX_PAYLOAD_FMT,
    14: TIME_TRIAL_PAYLOAD_FMT,
    15: LAP_POSITIONS_PAYLOAD_FMT,
    16: CAR_TELEMETRY2_PAYLOAD_FMT,
}


def _assert_layouts() -> None:
    """import 期自证：每个格式串的 payload 尺寸 == 官方 registry 的 expected_size - 29。"""
    # 延迟 import 避免循环依赖（packets.py 不依赖本文件，但显式声明更清晰）
    from protocol.f1_25_2026.packets import PACKET_REGISTRY

    for packet_id, definition in PACKET_REGISTRY.items():
        fmt = PACKET_PAYLOAD_FMT[packet_id]
        expected_payload = definition.expected_size - HEADER_SIZE
        actual = struct.calcsize(fmt)
        assert actual == expected_payload, (
            f"payload layout size mismatch for packet_id={packet_id} "
            f"({definition.packet_name}): calcsize={actual} != expected_payload={expected_payload}"
        )


_assert_layouts()
