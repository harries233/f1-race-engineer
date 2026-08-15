package com.f1.raceengineer.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

// F1 赛车红 + 碳纤暗色（与 f1-shanghai-setup「碳纤维王者」主题同源）
val F1Red = Color(0xFFE10600)
val Carbon = Color(0xFF101014)
val CarbonElevated = Color(0xFF1A1A20)
val Steel = Color(0xFF2A2A32)
val TextPrimary = Color(0xFFF2F2F4)
val TextMuted = Color(0xFF9A9AA4)
val Good = Color(0xFF2ECC71)
val Bad = Color(0xFFE74C3C)
val Warm = Color(0xFFF1C40F)

private val DarkColors = darkColorScheme(
    primary = F1Red,
    onPrimary = Color.White,
    background = Carbon,
    onBackground = TextPrimary,
    surface = CarbonElevated,
    onSurface = TextPrimary,
    surfaceVariant = Steel,
    onSurfaceVariant = TextMuted,
    secondary = TextMuted,
    onSecondary = Carbon,
    error = Bad,
)

@Composable
fun F1RaceEngineerTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    MaterialTheme(
        colorScheme = DarkColors,
        typography = MaterialTheme.typography,
        content = content,
    )
}
