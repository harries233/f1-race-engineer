# 发布新版本步骤

## 快速开始（推荐）

```bash
# 1. 先编辑 update.json 的 changelog（版本号不用改，脚本会处理）

# 2. 一键发布（构建 + 提交 + 打 tag + 推送 + 创建 GitHub Release + 刷新 CDN）
bash release.sh 1.0.1
```

脚本自动完成：
- 替换版本号（`android/app/build.gradle.kts` 的 versionCode+1 / versionName + `update.json` 的 version 与 URL 里的 vX.Y.Z）
- `build-apk.sh release` 构建 release 签名 APK
- 拷贝产物到仓库根 `F1-Race-Engineer.apk`（供 jsDelivr/raw 托管 + 提交）
- aapt 校验产物 versionCode / versionName
- 提交、打 tag `vX.Y.Z`、推送分支与 tag
- 用钥匙串 GitHub 凭据创建 Release 并上传 APK（幂等，已存在则复用/覆盖）
- purge jsDelivr 的 `@main/update.json`（关键：jsDelivr 缓存最长 12 小时，不刷新用户收不到更新）

前置要求：工作区干净、`~/.android/f1-re-release.jks` 签名已配置、git 凭据可用、**仓库已转公开**（六镜像链依赖公开访问）。

## 签名（一次性配置，已配置勿重复）

- keystore：`~/.android/f1-re-release.jks`（RSA 2048，30 年有效）
- 凭据：`~/.gradle/f1-re-release.properties`（chmod 600）
- 备份：`~/f1-keystore-backup/f1-re-release.{jks,properties}`

> ⚠ **与 f1-shanghai-setup 是两套独立密钥**（那是 `f1-release.jks`，这是 `f1-re-release.jks`），别混用。
>
> ⚠ **keystore 和密码必须备份**（如 iCloud/移动硬盘）。丢失 = 无法再为已安装用户发布更新（签名不一致，只能卸载重装）。密码存在 `~/.gradle/f1-re-release.properties` 里，建议同步记入密码管理器。

## 首次发布（v1.0.0）特别注意

1. **仓库转公开**：首次发布前把 `harries233/f1-race-engineer` 从 private 设为 public（否则 raw.githubusercontent.com / jsDelivr 全返回 404）。
2. **push 全部分支**：PHASE 14/15 等本地未 push 的 commit，会随 `release.sh` 的 `git push` 一次性推上去（首次发布即第二次 push checkpoint）。
3. **卸载 debug 旧版**：手机装过 `assembleDebug` 的 0.1.0（debug 签名）的，装 v1.0.0（正式签名）前需先卸载（签名不一致）。

## 手动发布（脚本不可用时的备选）

```bash
# 1. 改版本号（android/app/build.gradle.kts 的 versionCode+1 / versionName，update.json 的 version + vX.Y.Z）
# 2. 构建 + 拷贝产物
bash build-apk.sh release
cp android/app/build/outputs/apk/release/app-release.apk F1-Race-Engineer.apk
# 3. 提交推送
git add -A && git commit -m "v1.0.1" && git tag v1.0.1 && git push && git push origin v1.0.1
# 4. 创建 Release 并上传 APK
curl -X POST -H "Accept: application/vnd.github+json" -u "$GH_USER:$GH_TOKEN" \
  -d '{"tag_name":"v1.0.1","name":"F1 Race Engineer v1.0.1","body":"...","draft":false,"prerelease":false}' \
  https://api.github.com/repos/harries233/f1-race-engineer/releases
# 5. 刷新 jsDelivr（必做）
curl -X POST -H "Content-Type: application/json" \
  -d '{"path":["gh/harries233/f1-race-engineer@main/update.json"]}' \
  https://purge.jsdelivr.net
```

## 验证发布

```bash
# update.json 源头（purge 后 5 分钟内生效）
curl -s https://raw.githubusercontent.com/harries233/f1-race-engineer/main/update.json | head -3
# APK 镜像（tag 固定 URL 永久不变）
curl -s -o /dev/null -w "%{http_code}\n" \
  https://cdn.jsdelivr.net/gh/harries233/f1-race-engineer@v1.0.0/F1-Race-Engineer.apk
```

---

## 用户手机更新流程

1. **首次**：手动安装正式签名版 APK（或从 debug 版卸载后重装）。
2. 打开 App → 设置 →「检查更新」，或 App 启动时自动静默检查。
3. 有新版本 → 提示「新版本 vX.Y.Z 可用」→ 点下载。
4. 自动多镜像回退下载（进度条）→ 弹出系统安装界面 → 完成。
5. 若系统提示「不允许安装未知应用」→ 按提示开启后点「重试」。

无需手动配置更新地址；镜像链顺序（GitHub 直连 → jsDelivr 加速 → jsDelivr CDN → GitHub Release → 代理镜像）已按中国网络友好排序。
