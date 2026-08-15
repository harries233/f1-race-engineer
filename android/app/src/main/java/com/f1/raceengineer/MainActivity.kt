package com.f1.raceengineer

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import com.f1.raceengineer.ui.MainScreen
import com.f1.raceengineer.ui.theme.F1RaceEngineerTheme
import com.f1.raceengineer.update.UpdateInfo
import com.f1.raceengineer.update.UpdateManager
import com.f1.raceengineer.vm.AppViewModel
import kotlinx.coroutines.launch

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            F1RaceEngineerTheme {
                val vm: AppViewModel = viewModel()
                val context = LocalContext.current
                val updateManager = remember { UpdateManager(context) }
                val scope = rememberCoroutineScope()
                var pendingUpdate by remember { mutableStateOf<UpdateInfo?>(null) }

                // 启动静默检查 OTA 更新
                LaunchedEffect(Unit) {
                    pendingUpdate = updateManager.checkForUpdate()
                }

                MainScreen(vm)

                pendingUpdate?.let { info ->
                    AlertDialog(
                        onDismissRequest = { pendingUpdate = null },
                        title = { Text("发现新版本 v${info.version}") },
                        text = { Text(info.changelog.ifBlank { "有新版本可用。" }) },
                        confirmButton = {
                            TextButton(
                                onClick = {
                                    pendingUpdate = null
                                    scope.launch {
                                        runCatching { updateManager.downloadApk(info) }
                                            .onSuccess { updateManager.installApk(it) }
                                            .onFailure {
                                                // 下载失败：静默忽略，下次启动再试
                                            }
                                    }
                                },
                            ) { Text("更新") }
                        },
                        dismissButton = {
                            TextButton(onClick = { pendingUpdate = null }) { Text("以后") }
                        },
                        containerColor = MaterialTheme.colorScheme.surface,
                    )
                }
            }
        }
    }
}
