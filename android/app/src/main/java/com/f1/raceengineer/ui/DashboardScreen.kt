package com.f1.raceengineer.ui

import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.f1.raceengineer.net.SocketStatus
import com.f1.raceengineer.net.formatLapTime
import com.f1.raceengineer.net.optDoubleOrNull
import com.f1.raceengineer.net.optIntOrNull
import com.f1.raceengineer.ui.components.EmptyHint
import com.f1.raceengineer.ui.components.MetricRow
import com.f1.raceengineer.ui.components.SectionCard
import com.f1.raceengineer.ui.components.SectionTitle
import com.f1.raceengineer.ui.components.SourceBadge
import com.f1.raceengineer.ui.components.LapsChart
import com.f1.raceengineer.ui.theme.F1Red
import com.f1.raceengineer.ui.theme.Good
import com.f1.raceengineer.ui.theme.TextMuted
import com.f1.raceengineer.ui.theme.Warm
import com.f1.raceengineer.vm.AppViewModel
import org.json.JSONObject

@Composable
fun DashboardScreen(vm: AppViewModel, modifier: Modifier = Modifier) {
    val status by vm.socketStatus.collectAsStateWithLifecycle()
    val live by vm.liveTelemetry.collectAsStateWithLifecycle()
    val session by vm.session.collectAsStateWithLifecycle()
    val laps by vm.laps.collectAsStateWithLifecycle()
    val sectors by vm.sectors.collectAsStateWithLifecycle()
    val corners by vm.corners.collectAsStateWithLifecycle()

    if (!vm.serverConfigured) {
        Column(
            modifier = modifier.fillMaxSize().padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Text("未配置后端", fontSize = 20.sp, fontWeight = FontWeight.Bold)
            Text(
                "请到「设置」页填写后端地址（局域网 IP + 端口），再回到这里连接。",
                color = TextMuted,
                modifier = Modifier.padding(top = 8.dp),
            )
        }
        return
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        // 连接状态
        SectionCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("连接状态", fontSize = 12.sp, color = TextMuted)
                    Text(
                        when (status) {
                            SocketStatus.CONNECTED -> "已连接（实时遥测）"
                            SocketStatus.CONNECTING -> "连接中…"
                            SocketStatus.DISCONNECTED -> "未连接"
                        },
                        fontSize = 16.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (status == SocketStatus.CONNECTED) Good else Warm,
                    )
                }
                if (status == SocketStatus.CONNECTED) {
                    OutlinedButton(onClick = { vm.disconnect() }) { Text("断开") }
                } else {
                    Button(onClick = { vm.connect() }) { Text("连接") }
                }
            }
        }

        // 实时遥测
        LiveTelemetryCard(live)

        // 会话上下文
        SectionCard {
            SectionTitle("会话")
            session?.let {
                SourceBadge("RAW", "HIGH")
                val track = it.optString("track_name", it.optString("track_id", "—"))
                MetricRow("赛道", track)
                MetricRow("天气(枚举)", it.optIntOrNull("m_weather")?.toString() ?: "—")
                MetricRow("赛道温度", it.optIntOrNull("m_trackTemperature")?.let { t -> "$t °C" } ?: "—")
                MetricRow("气温", it.optIntOrNull("m_airTemperature")?.let { t -> "$t °C" } ?: "—")
                MetricRow("总圈数", it.optIntOrNull("m_totalLaps")?.toString() ?: "—")
            } ?: EmptyHint("无 Session 数据（确认后端已收到 UDP）")
        }

        // 圈速
        SectionCard {
            SectionTitle("圈速")
            val lapPairs = laps.mapNotNull { l ->
                l.optIntOrNull("lap_number")?.let { n ->
                    l.optDoubleOrNull("lap_time")?.let { t -> n to t }
                }
            }
            if (lapPairs.isEmpty()) {
                EmptyHint("无完赛圈数据")
            } else {
                LapsChart(lapPairs)
                val best = lapPairs.minByOrNull { it.second }
                best?.let { MetricRow("最快圈", formatLapTime(it.second) + "  (L${it.first})") }
                Column(Modifier.padding(top = 8.dp)) {
                    laps.takeLast(8).reversed().forEach { l ->
                        val n = l.optIntOrNull("lap_number")
                        val t = l.optDoubleOrNull("lap_time")
                        val valid = l.optBoolean("valid_flag")
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("L$n", color = TextMuted, fontSize = 13.sp)
                            Text(
                                formatLapTime(t),
                                fontSize = 14.sp,
                                fontWeight = FontWeight.SemiBold,
                                color = if (valid) MaterialTheme.colorScheme.onBackground else TextMuted,
                            )
                        }
                    }
                }
            }
        }

        // 扇区（最新圈）
        val latestLap = laps.mapNotNull { it.optIntOrNull("lap_number") }.maxOrNull()
        val latestSectors = sectors.filter { it.optIntOrNull("lap_number") == latestLap }
        SectionCard {
            SectionTitle("扇区（L$latestLap）")
            if (latestSectors.isEmpty()) {
                EmptyHint("无扇区数据")
            } else {
                latestSectors.sortedBy { it.optIntOrNull("sector_index") }.forEach { s ->
                    val idx = s.optIntOrNull("sector_index")?.plus(1) ?: 0
                    val t = s.optDoubleOrNull("sector_time")
                    val minSpd = s.optDoubleOrNull("min_speed")
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("S$idx", color = TextMuted, fontSize = 13.sp)
                        Text(formatLapTime(t), fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
                        Text(if (minSpd != null) "min %.0f km/h".format(minSpd) else "—", color = TextMuted, fontSize = 12.sp)
                    }
                }
            }
        }

        // 弯角（最新圈）
        val latestCorners = corners.filter { it.optIntOrNull("lap_number") == latestLap }
        SectionCard {
            SectionTitle("弯角（L$latestLap）")
            if (latestCorners.isEmpty()) {
                EmptyHint("无弯角数据")
            } else {
                latestCorners.sortedBy { it.optIntOrNull("corner_number") }.forEach { c ->
                    val cn = c.optIntOrNull("corner_number") ?: 0
                    val minSpd = c.optDoubleOrNull("mid_min_speed")
                    val exitSpd = c.optDoubleOrNull("exit_speed")
                    val phase = c.optString("time_loss_phase")
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text("弯 $cn", color = TextMuted, fontSize = 13.sp)
                        Text(
                            if (minSpd != null) "min %.0f".format(minSpd) else "—",
                            fontSize = 13.sp,
                            fontWeight = FontWeight.SemiBold,
                        )
                        Text(
                            if (exitSpd != null) "exit %.0f".format(exitSpd) else "—",
                            fontSize = 13.sp,
                            color = TextMuted,
                        )
                        if (phase.isNotEmpty() && phase != "null") {
                            Text(phase, fontSize = 11.sp, color = Warm)
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(8.dp))
    }
}

@Composable
private fun LiveTelemetryCard(live: Map<String, JSONObject>) {
    val tele = live["car_telemetry"]
    val status = live["car_status"]
    val lap = live["lap_data"]

    val speed = tele?.optDoubleOrNull("m_speed")
    val gear = tele?.optIntOrNull("m_gear")
    val rpm = tele?.optIntOrNull("m_engineRPM")
    val throttle = tele?.optDoubleOrNull("m_throttle")
    val brake = tele?.optDoubleOrNull("m_brake")
    val fuel = status?.optDoubleOrNull("m_fuelInTank")
    val fuelCap = status?.optDoubleOrNull("m_fuelCapacity")
    val ers = status?.optDoubleOrNull("m_ersStoreEnergy")
    val curLap = lap?.optIntOrNull("m_currentLapNum")
    val sector = lap?.optIntOrNull("m_sector")

    SectionCard {
        SectionTitle("实时遥测")
        if (speed == null) {
            EmptyHint("等待实时数据…（连接 WS 后自动更新）")
            return@SectionCard
        }
        Row(verticalAlignment = Alignment.Bottom) {
            Text(
                speed.toInt().toString(),
                fontSize = 56.sp,
                fontWeight = FontWeight.Bold,
                color = F1Red,
            )
            Text(" km/h", fontSize = 16.sp, color = TextMuted, modifier = Modifier.padding(bottom = 10.dp))
            Spacer(Modifier.weight(1f))
            Column(horizontalAlignment = Alignment.End) {
                Text("挡位", fontSize = 11.sp, color = TextMuted)
                Text(gear?.toString() ?: "—", fontSize = 28.sp, fontWeight = FontWeight.Bold)
            }
        }
        Row(Modifier.padding(top = 8.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            MetricRow("转速", rpm?.toString() ?: "—", Modifier.weight(1f))
            MetricRow("当前圈", curLap?.toString() ?: "—", Modifier.weight(1f))
            MetricRow("扇区", sector?.plus(1)?.toString() ?: "—", Modifier.weight(1f))
        }

        // 油门 / 刹车
        Row(Modifier.padding(top = 12.dp), verticalAlignment = Alignment.CenterVertically) {
            Text("油门", fontSize = 12.sp, color = TextMuted, modifier = Modifier.width(40.dp))
            LinearProgressIndicator(
                progress = { normalize01(throttle) },
                modifier = Modifier.weight(1f).height(8.dp),
                color = Good,
                trackColor = MaterialTheme.colorScheme.surfaceVariant,
            )
            Spacer(Modifier.width(10.dp))
            Text("刹车", fontSize = 12.sp, color = TextMuted, modifier = Modifier.width(40.dp))
            LinearProgressIndicator(
                progress = { normalize01(brake) },
                modifier = Modifier.weight(1f).height(8.dp),
                color = F1Red,
                trackColor = MaterialTheme.colorScheme.surfaceVariant,
            )
        }

        Row(Modifier.padding(top = 12.dp), horizontalArrangement = Arrangement.spacedBy(16.dp)) {
            val fuelText = if (fuel != null && fuelCap != null && fuelCap > 0)
                "%.1f / %.0f L".format(fuel, fuelCap) else "—"
            MetricRow("燃油", fuelText, Modifier.weight(1f))
            MetricRow("ERS", if (ers != null) "%.0f".format(ers) else "—", Modifier.weight(1f))
        }
    }
}

/** F1 m_throttle/m_brake 为 0–100（%），归一化到 0..1 供进度条。 */
private fun normalize01(v: Double?): Float =
    if (v == null) 0f else (v / 100.0).toFloat().coerceIn(0f, 1f)
