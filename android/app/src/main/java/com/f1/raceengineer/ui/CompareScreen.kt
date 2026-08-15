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
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.f1.raceengineer.net.optDoubleOrNull
import com.f1.raceengineer.ui.components.EmptyHint
import com.f1.raceengineer.ui.components.MetricRow
import com.f1.raceengineer.ui.components.SectionCard
import com.f1.raceengineer.ui.components.SectionTitle
import com.f1.raceengineer.ui.components.SourceBadge
import com.f1.raceengineer.ui.theme.Bad
import com.f1.raceengineer.ui.theme.Good
import com.f1.raceengineer.ui.theme.TextMuted
import com.f1.raceengineer.ui.theme.Warm
import com.f1.raceengineer.vm.AppViewModel
import org.json.JSONObject

@Composable
fun CompareScreen(vm: AppViewModel, modifier: Modifier = Modifier) {
    val result by vm.compareResult.collectAsStateWithLifecycle()
    val experiments by vm.experiments.collectAsStateWithLifecycle()
    val recommendations by vm.recommendations.collectAsStateWithLifecycle()
    val busy by vm.busy.collectAsStateWithLifecycle()

    var baselineText by remember { mutableStateOf("") }
    var testText by remember { mutableStateOf("") }

    Column(
        modifier = modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        SectionCard {
            SectionTitle("A-B 圈速对比")
            Text(
                "delta = test − baseline（负 = test 更快）。圈号用逗号分隔，如 1,2,3。",
                fontSize = 12.sp,
                color = TextMuted,
            )
            OutlinedTextField(
                value = baselineText,
                onValueChange = { baselineText = it },
                label = { Text("Baseline 圈号") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            OutlinedTextField(
                value = testText,
                onValueChange = { testText = it },
                label = { Text("Test 圈号") },
                modifier = Modifier.fillMaxWidth(),
                singleLine = true,
            )
            Button(
                onClick = {
                    vm.compare(parseLaps(baselineText), parseLaps(testText))
                },
                enabled = !busy,
                modifier = Modifier.fillMaxWidth().padding(top = 8.dp),
            ) { Text(if (busy) "计算中…" else "对比") }
        }

        result?.let { CompareResultCard(it) }

        SectionCard {
            SectionTitle("Setup 推荐")
            if (recommendations.isEmpty()) {
                EmptyHint("无推荐（AI 经 /api/ask 产出后可在此查看）")
            } else {
                recommendations.take(5).forEach { r ->
                    RecommendationRow(r)
                }
            }
        }

        SectionCard {
            SectionTitle("实验记录")
            if (experiments.isEmpty()) {
                EmptyHint("无实验")
            } else {
                experiments.take(5).forEach { e ->
                    ExperimentRow(e)
                }
            }
        }

        Spacer(Modifier.height(8.dp))
    }
}

private fun parseLaps(text: String): List<Int> =
    text.split(',', '，', ' ').mapNotNull { it.trim().toIntOrNull() }

@Composable
private fun CompareResultCard(r: JSONObject) {
    SectionCard {
        SectionTitle("对比结果")
        SourceBadge("DERIVED", r.optString("confidence").ifBlank { "HIGH" })
        val best = r.optDoubleOrNull("best_delta_s")
        val mean = r.optDoubleOrNull("mean_delta_s")
        MetricRow("样本", "baseline ${r.optInt("baseline_n")} vs test ${r.optInt("test_n")}")
        best?.let {
            MetricRow(
                "最快圈 delta",
                (if (it <= 0) "-" else "+") + "%.3f s".format(kotlin.math.abs(it)),
            )
        }
        mean?.let {
            MetricRow(
                "平均 delta",
                (if (it <= 0) "-" else "+") + "%.3f s".format(kotlin.math.abs(it)),
            )
        }
        Text(
            verdict(best),
            fontSize = 15.sp,
            fontWeight = FontWeight.Bold,
            color = when {
                best == null -> TextMuted
                best < 0 -> Good
                best > 0 -> Bad
                else -> Warm
            },
            modifier = Modifier.padding(top = 8.dp),
        )
    }
}

private fun verdict(bestDelta: Double?): String = when {
    bestDelta == null -> "无有效圈，无法判定（NO DATA → NO FACT）"
    bestDelta < 0 -> "TEST 更快 ✅"
    bestDelta > 0 -> "TEST 更慢 ❌"
    else -> "持平"
}

@Composable
private fun RecommendationRow(r: JSONObject) {
    val summary = r.optString("summary", "—")
    val status = r.optString("status", "PREDICTED")
    val conf = r.optString("confidence", "LOW")
    Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text(summary, fontSize = 14.sp, fontWeight = FontWeight.SemiBold, modifier = Modifier.weight(1f))
            SourceBadge("HYPOTHESIS", conf)
        }
        Text("状态 $status", fontSize = 12.sp, color = TextMuted)
    }
}

@Composable
private fun ExperimentRow(e: JSONObject) {
    val exp = e.optString("exp_id", "—")
    val hyp = e.optString("hypothesis", "—")
    val status = e.optString("status", "—")
    Column(Modifier.fillMaxWidth().padding(vertical = 6.dp)) {
        Row(horizontalArrangement = Arrangement.SpaceBetween, modifier = Modifier.fillMaxWidth()) {
            Text(exp, fontSize = 13.sp, fontWeight = FontWeight.SemiBold)
            Text(status, fontSize = 12.sp, color = Warm)
        }
        Text(hyp, fontSize = 12.sp, color = TextMuted)
    }
}
