package com.f1.raceengineer.ui

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Button
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.f1.raceengineer.ui.theme.F1Red
import com.f1.raceengineer.ui.theme.TextMuted
import com.f1.raceengineer.vm.AppViewModel
import com.f1.raceengineer.vm.ChatMessage

@Composable
fun ChatScreen(vm: AppViewModel, modifier: Modifier = Modifier) {
    val chat by vm.chat.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()
    var input by remember { mutableStateOf("") }

    Column(modifier = modifier.fillMaxSize().padding(16.dp)) {
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.fillMaxWidth(),
        ) {
            Text(
                "AI Race Engineer",
                fontSize = 18.sp,
                fontWeight = FontWeight.Bold,
                modifier = Modifier.weight(1f),
            )
            TextButton(onClick = { vm.clearChat() }) { Text("清空", color = TextMuted) }
        }

        LazyColumn(
            modifier = Modifier.weight(1f).padding(top = 8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (chat.isEmpty()) {
                item {
                    Text(
                        "问我任何关于本次练习的数据问题，例如：\n「我哪一圈最快？S2 有什么可以改进？」",
                        color = TextMuted,
                        fontSize = 13.sp,
                    )
                }
            }
            items(chat) { msg -> Bubble(msg) }
        }

        Row(
            modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            OutlinedTextField(
                value = input,
                onValueChange = { input = it },
                placeholder = { Text("问一个数据问题…") },
                modifier = Modifier.weight(1f),
                maxLines = 3,
            )
            Button(
                onClick = {
                    vm.ask(input)
                    input = ""
                },
                enabled = input.isNotBlank() && !busy,
                modifier = Modifier.padding(start = 8.dp),
            ) { Text(if (busy) "…" else "发送") }
        }
    }
}

@Composable
private fun Bubble(msg: ChatMessage) {
    val isUser = msg.role == ChatMessage.Role.USER
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        val bg = if (isUser) F1Red.copy(alpha = 0.18f) else MaterialTheme.colorScheme.surfaceVariant
        Text(
            text = msg.text,
            color = MaterialTheme.colorScheme.onBackground,
            fontSize = 14.sp,
            modifier = Modifier
                .background(bg, RoundedCornerShape(12.dp))
                .padding(horizontal = 12.dp, vertical = 8.dp),
        )
    }
}
