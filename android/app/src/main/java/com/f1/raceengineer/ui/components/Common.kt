package com.f1.raceengineer.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.f1.raceengineer.ui.theme.Bad
import com.f1.raceengineer.ui.theme.Good
import com.f1.raceengineer.ui.theme.TextMuted
import com.f1.raceengineer.ui.theme.Warm

/** source_level 徽标色：实测偏绿、数据偏蓝、推测偏黄（诚实区分数据来源）。 */
private fun levelColor(level: String): Color = when (level.uppercase()) {
    "RAW", "DERIVED", "VALIDATED" -> Good
    "GAME_DATA" -> Color(0xFF4FA3E3)
    "MODEL", "HYPOTHESIS" -> Warm
    else -> TextMuted
}

/** 信封徽标：`source_level · confidence`，UI 显式声明这条数据是实测还是推测。 */
@Composable
fun SourceBadge(sourceLevel: String?, confidence: String?, modifier: Modifier = Modifier) {
    if (sourceLevel.isNullOrBlank() && confidence.isNullOrBlank()) return
    Row(
        modifier = modifier,
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        if (!sourceLevel.isNullOrBlank()) {
            Badge(text = sourceLevel, color = levelColor(sourceLevel))
        }
        if (!confidence.isNullOrBlank()) {
            Badge(text = confidence, color = TextMuted)
        }
    }
}

@Composable
private fun Badge(text: String, color: Color) {
    Text(
        text = text.uppercase(),
        color = color,
        fontSize = 10.sp,
        fontWeight = FontWeight.Bold,
        letterSpacing = 0.5.sp,
        modifier = Modifier
            .background(color.copy(alpha = 0.14f), RoundedCornerShape(4.dp))
            .padding(horizontal = 6.dp, vertical = 2.dp),
    )
}

/** 区块标题。 */
@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text,
        style = MaterialTheme.typography.titleSmall,
        color = MaterialTheme.colorScheme.onBackground,
        modifier = modifier.padding(bottom = 8.dp),
    )
}

/** 通用卡片容器（暗色 surface）。 */
@Composable
fun SectionCard(modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    Card(
        modifier = modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surface,
        ),
        shape = RoundedCornerShape(12.dp),
    ) {
        Column(modifier = Modifier.padding(14.dp)) { content() }
    }
}

/** 标签—值 行。 */
@Composable
fun MetricRow(label: String, value: String, modifier: Modifier = Modifier) {
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(text = label, color = TextMuted, fontSize = 13.sp)
        Text(
            text = value,
            color = MaterialTheme.colorScheme.onBackground,
            fontSize = 14.sp,
            fontWeight = FontWeight.SemiBold,
        )
    }
}

/** 空状态占位。 */
@Composable
fun EmptyHint(text: String, modifier: Modifier = Modifier) {
    Text(
        text = text,
        color = TextMuted,
        fontSize = 13.sp,
        modifier = modifier.padding(vertical = 12.dp),
    )
}
