package com.f1.raceengineer.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.provider.Settings
import androidx.core.content.FileProvider
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.OkHttpClient
import okhttp3.Request
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.util.concurrent.TimeUnit

/**
 * OTA 自动更新（参考 f1-shanghai-setup 的六镜像链，中国网络友好）。
 *
 * 流程：启动时静默检查 update.json（多镜像回退）→ 版本号大于本地则提示 →
 * 用户确认后逐源回退下载 APK → FileProvider + ACTION_VIEW 触发系统安装。
 *
 * 说明：仓库已转公开（2026-08-15），六镜像链（raw → jsDelivr → GitHub Release → ghproxy）
 * 全部可用；update.json 在仓库根、APK 以 F1-Race-Engineer.apk 提交到 main 并打 tag 固定 URL。
 * 首次发布走 `bash release.sh <版本号>`（见根 RELEASE.md）。
 */
data class UpdateInfo(
    val version: String,
    val changelog: String,
    val apkUrls: List<String>,
)

class UpdateManager(private val context: Context) {

    private val client = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(120, TimeUnit.SECONDS)
        .followRedirects(true)
        .build()

    // update.json 多镜像（顺序即回退优先级）。仓库公开后可切换 @main → @vX.Y.Z 固定 tag。
    private val updateJsonUrls = listOf(
        "https://raw.githubusercontent.com/harries233/f1-race-engineer/main/update.json",
        "https://fastly.jsdelivr.net/gh/harries233/f1-race-engineer@main/update.json",
        "https://cdn.jsdelivr.net/gh/harries233/f1-race-engineer@main/update.json",
    )

    /** 静默检查：返回可用的新版本信息；无更新 / 网络失败返回 null。 */
    suspend fun checkForUpdate(): UpdateInfo? = withContext(Dispatchers.IO) {
        val localVersion = versionName()
        for (url in updateJsonUrls) {
            val info = runCatching { fetchUpdateInfo(url) }.getOrNull() ?: continue
            if (isNewer(info.version, localVersion) && info.apkUrls.isNotEmpty()) return@withContext info
            return@withContext null // 拿到有效清单但版本未超 → 无需更新，不再试其它源
        }
        null
    }

    private fun fetchUpdateInfo(url: String): UpdateInfo {
        val req = Request.Builder().url(url).build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw IllegalStateException("HTTP ${resp.code}")
            val json = JSONObject(resp.body?.string() ?: throw IllegalStateException("空响应"))
            val apkUrls = buildList {
                json.optJSONArray("apkUrls")?.let { arr ->
                    for (i in 0 until arr.length()) {
                        arr.optJSONObject(i)?.optString("url")?.takeIf { it.isNotBlank() }?.let(::add)
                    }
                }
                json.optString("apkUrl").takeIf { it.isNotBlank() }?.let(::add)
            }.distinct()
            return UpdateInfo(
                version = json.optString("version"),
                changelog = json.optString("changelog"),
                apkUrls = apkUrls,
            )
        }
    }

    /** 逐源回退下载 APK，返回落地文件；全部失败抛异常。 */
    suspend fun downloadApk(info: UpdateInfo, onProgress: (Int) -> Unit = {}): File =
        withContext(Dispatchers.IO) {
            val dir = context.getExternalFilesDir(Environment.DIRECTORY_DOWNLOADS)
                ?: context.filesDir
            val apk = File(dir, "f1-race-engineer-update.apk")
            var lastError: Exception? = null
            for (url in info.apkUrls) {
                try {
                    downloadSingle(url, apk, onProgress)
                    if (apk.length() > MIN_APK_SIZE) return@withContext apk
                    lastError = IllegalStateException("文件过小(${apk.length()}B)")
                } catch (e: Exception) {
                    lastError = e
                }
            }
            throw IllegalStateException("所有下载源均失败", lastError)
        }

    private fun downloadSingle(url: String, out: File, onProgress: (Int) -> Unit) {
        val req = Request.Builder().url(url).build()
        client.newCall(req).execute().use { resp ->
            if (!resp.isSuccessful) throw IllegalStateException("HTTP ${resp.code}")
            val total = resp.body?.contentLength() ?: -1
            if (total in 1 until MIN_APK_SIZE) throw IllegalStateException("文件过小(${total}B)")
            resp.body?.byteStream()?.use { input ->
                FileOutputStream(out).use { output ->
                    val buf = ByteArray(64 * 1024)
                    var done = 0L
                    while (true) {
                        val n = input.read(buf)
                        if (n < 0) break
                        output.write(buf, 0, n)
                        done += n
                        if (total > 0) onProgress((done * 100 / total).toInt())
                    }
                }
            }
        }
    }

    /** 触发系统安装界面（Android 8+ 需「允许安装未知应用」）。 */
    fun installApk(apk: File): Boolean {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O &&
            !context.packageManager.canRequestPackageInstalls()
        ) {
            runCatching {
                context.startActivity(
                    Intent(
                        Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES,
                        Uri.parse("package:${context.packageName}"),
                    ).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK),
                )
            }
            return false
        }
        return runCatching {
            val uri = FileProvider.getUriForFile(
                context,
                "${context.packageName}.fileprovider",
                apk,
            )
            val intent = Intent(Intent.ACTION_VIEW).apply {
                setDataAndType(uri, "application/vnd.android.package-archive")
                flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_GRANT_READ_URI_PERMISSION
            }
            context.startActivity(intent)
        }.isSuccess
    }

    private fun versionName(): String = runCatching {
        context.packageManager.getPackageInfo(context.packageName, 0).versionName ?: "0.0.0"
    }.getOrDefault("0.0.0")

    private fun isNewer(candidate: String, current: String): Boolean =
        compareVersions(candidate, current) > 0

    /** 语义化版本比较：a > b 返回正数。非标准号段按 0 处理。 */
    private fun compareVersions(a: String, b: String): Int {
        val pa = a.split('.').map { it.toIntOrNull() ?: 0 }
        val pb = b.split('.').map { it.toIntOrNull() ?: 0 }
        val n = maxOf(pa.size, pb.size)
        for (i in 0 until n) {
            val x = pa.getOrElse(i) { 0 }
            val y = pb.getOrElse(i) { 0 }
            if (x != y) return x - y
        }
        return 0
    }

    companion object {
        // 最小 APK 体积校验：挡住 HTML 错误页等垃圾内容（正式包远大于此）。
        private const val MIN_APK_SIZE = 100 * 1024L
    }
}
