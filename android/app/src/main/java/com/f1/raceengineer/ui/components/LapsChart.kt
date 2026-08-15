package com.f1.raceengineer.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import com.f1.raceengineer.ui.theme.F1Red
import com.f1.raceengineer.ui.theme.TextMuted

/**
 * 圈速折线图（纯 Canvas，零图表依赖）。
 *
 * 输入为「圈号 → 圈速(秒)」序列，纵轴取数据自身 min/max 留白归一化；
 * 有效圈连实线，缺失圈速的圈断开（不画线段）。红线 = 最快圈。
 */
@Composable
fun LapsChart(
    laps: List<Pair<Int, Double>>,
    modifier: Modifier = Modifier,
) {
    if (laps.isEmpty()) return

    val minLap = laps.minOf { it.first }
    val maxLap = laps.maxOf { it.first }
    val times = laps.map { it.second }.filter { it.isFinite() }
    if (times.isEmpty()) return
    val minTime = times.min()
    val maxTime = times.max()
    val span = (maxTime - minTime).coerceAtLeast(0.001)
    val bestLap = laps.filter { it.second.isFinite() }.minByOrNull { it.second }?.first

    Canvas(modifier = modifier.fillMaxWidth().height(180.dp)) {
        val pad = 24.dp.toPx()
        val w = size.width - pad * 2
        val h = size.height - pad * 2

        fun x(lap: Int): Float = pad + w * (lap - minLap).toFloat() / (maxLap - minLap).coerceAtLeast(1)
        fun y(t: Double): Float = pad + h * (1 - (t - minTime).toFloat() / span.toFloat())

        // 参考线：最快圈速
        val bestY = y(minTime)
        drawLine(
            color = F1Red.copy(alpha = 0.35f),
            start = Offset(pad, bestY),
            end = Offset(size.width - pad, bestY),
            strokeWidth = 2.dp.toPx(),
        )

        // 折线（缺失圈断开）
        var prev: Pair<Int, Double>? = null
        for ((lap, t) in laps) {
            if (t.isFinite()) {
                prev?.let { (pl, pt) ->
                    if (pt.isFinite() && lap == pl + 1) {
                        drawLine(
                            color = if (lap == bestLap) F1Red else TextMuted,
                            start = Offset(x(pl), y(pt)),
                            end = Offset(x(lap), y(t)),
                            strokeWidth = 2.5.dp.toPx(),
                            cap = StrokeCap.Round,
                        )
                    }
                }
                prev = lap to t
            }
        }

        // 数据点 + 最快圈高亮
        laps.filter { it.second.isFinite() }.forEach { (lap, t) ->
            val r = if (lap == bestLap) 5.dp.toPx() else 3.dp.toPx()
            drawCircle(
                color = if (lap == bestLap) F1Red else TextMuted,
                radius = r,
                center = Offset(x(lap), y(t)),
            )
            if (lap == bestLap) {
                drawCircle(
                    color = F1Red.copy(alpha = 0.25f),
                    radius = r * 2.2f,
                    center = Offset(x(lap), y(t)),
                    style = Stroke(width = 1.dp.toPx()),
                )
            }
        }

        // 圈号刻度（首尾）
        drawLine(
            color = TextMuted.copy(alpha = 0.4f),
            start = Offset(pad, size.height - pad),
            end = Offset(size.width - pad, size.height - pad),
            strokeWidth = 1.dp.toPx(),
        )
    }
}
