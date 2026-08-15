package com.f1.raceengineer.ui

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Button
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.f1.raceengineer.ui.components.SectionCard
import com.f1.raceengineer.ui.components.SectionTitle
import com.f1.raceengineer.ui.theme.TextMuted
import com.f1.raceengineer.vm.AppViewModel

@Composable
fun SettingsScreen(vm: AppViewModel, modifier: Modifier = Modifier) {
    var host by remember { mutableStateOf(vm.serverHost) }
    var port by remember { mutableIntStateOf(vm.serverPort) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        SectionCard {
            SectionTitle("后端连接")
            Text(
                "后端是同一局域网内跑 FastAPI 的电脑（`python scripts/serve.py`）。填它的 IP 与端口。",
                fontSize = 12.sp,
                color = TextMuted,
            )
            OutlinedTextField(
                value = host,
                onValueChange = { host = it },
                label = { Text("主机 IP") },
                placeholder = { Text("192.168.1.10") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            OutlinedTextField(
                value = port.toString(),
                onValueChange = { port = it.toIntOrNull() ?: 0 },
                label = { Text("端口") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            Row(
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                Button(onClick = { vm.saveServer(host, port) }, modifier = Modifier.weight(1f)) {
                    Text("保存")
                }
                OutlinedButton(onClick = { vm.testConnection() }, modifier = Modifier.weight(1f)) {
                    Text("测试连接")
                }
            }
        }

        SectionCard {
            SectionTitle("关于")
            Text("F1 25 AI Race Engineer · 手机端薄客户端", fontWeight = FontWeight.SemiBold)
            Text(
                "只显示后端算好的数据与 AI 回答，不计算、不碰 UDP。数据来源等级（RAW/DERIVED/HYPOTHESIS）全程显式标注。",
                fontSize = 12.sp,
                color = TextMuted,
            )
        }

        Spacer(Modifier.height(8.dp))
    }
}
