package com.f1.raceengineer.ui

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.f1.raceengineer.ui.theme.F1Red
import com.f1.raceengineer.ui.theme.TextMuted
import com.f1.raceengineer.vm.AppViewModel

private enum class Tab(val label: String, val glyph: String) {
    DASHBOARD("仪表盘", "🏎"),
    COMPARE("对比", "⚖"),
    CHAT("AI", "💬"),
    SETTINGS("设置", "⚙"),
}

@Composable
fun MainScreen(vm: AppViewModel) {
    var tab by rememberSaveable { androidx.compose.runtime.mutableStateOf(Tab.DASHBOARD.name) }
    val snackbarHostState = remember { SnackbarHostState() }
    val statusMessage by vm.statusMessage.collectAsStateWithLifecycle()

    LaunchedEffect(statusMessage) {
        statusMessage?.let {
            snackbarHostState.showSnackbar(it)
            vm.consumeStatus()
        }
    }

    Scaffold(
        snackbarHost = { SnackbarHost(snackbarHostState) },
        bottomBar = { BottomBar(tab) { tab = it } },
        containerColor = MaterialTheme.colorScheme.background,
    ) { padding ->
        when (Tab.valueOf(tab)) {
            Tab.DASHBOARD -> DashboardScreen(vm, Modifier.padding(padding))
            Tab.COMPARE -> CompareScreen(vm, Modifier.padding(padding))
            Tab.CHAT -> ChatScreen(vm, Modifier.padding(padding))
            Tab.SETTINGS -> SettingsScreen(vm, Modifier.padding(padding))
        }
    }
}

@Composable
private fun BottomBar(selected: String, onSelect: (String) -> Unit) {
    Surface(color = MaterialTheme.colorScheme.surface) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(vertical = 6.dp),
            horizontalArrangement = Arrangement.SpaceEvenly,
        ) {
            Tab.entries.forEach { t ->
                val active = t.name == selected
                Column(
                    modifier = Modifier
                        .clickable { onSelect(t.name) }
                        .padding(horizontal = 14.dp, vertical = 4.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Text(text = t.glyph, fontSize = 20.sp)
                    Text(
                        text = t.label,
                        fontSize = 11.sp,
                        fontWeight = if (active) FontWeight.Bold else FontWeight.Normal,
                        color = if (active) F1Red else TextMuted,
                    )
                }
            }
        }
    }
}
