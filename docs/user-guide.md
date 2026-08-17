# F1 25 AI Race Engineer — 使用教程

> 版本：v1.0.0（2026-08-15 首次发布）
> 面向用户：F1 25（含 2026 Season Pack DLC）玩家，想要一位 AI 车组工程师实时读遥测、给 Setup 建议、做圈速对比的人。
> 本文以 **Windows 电脑跑后端 + 游戏**、**Android 手机连入** 为主要场景（macOS 对照见括号内）。

---

## 1. 这是什么

一套「**赛车遥测 → AI 分析 → Setup 建议**」的本地系统，由两部分组成：

- **后端**（跑在你电脑上，Python）：接收游戏实时 UDP 遥测 → 校验 → 存库 → 确定性计算圈速/扇区/逐弯指标 → 用 AI 分析并给调车建议。
- **手机端**（Android App）：通过同一局域网连到后端，实时显示仪表盘、圈速、扇区、逐弯数据，看 AI 建议、跟 AI 对话、对比调校前后差异。

核心原则：**AI 不凭空给数字**。每个数据都标注来源等级（`RAW` 实测 / `DERIVED` 计算 / `HYPOTHESIS` 推测），可信度一目了然。

```
┌─────────────┐   UDP 遥测   ┌──────────────────┐   HTTP/WS   ┌─────────────┐
│  F1 25 游戏  │ ───────────→ │  后端 (电脑/Python) │ ←──────────→ │  手机 App    │
│ (2026 Pack) │              │  接收/校验/计算/AI │             │ 仪表盘/AI/对比 │
└─────────────┘              └──────────────────┘             └─────────────┘
```

---

## 2. 快速开始（三步）

### 第一步：启动后端（Windows 电脑）

打开 **PowerShell**，进入项目目录：

```powershell
cd C:\你的路径\f1-race-engineer      # 换成你解压/克隆项目的实际路径
.venv\Scripts\activate                # 激活虚拟环境（首次安装见 §3.1）

# 启动服务：HTTP 端口 8000，UDP 端口 20777（端口可自选，见 §4）
python scripts\serve.py --db telemetry.sqlite3 --port 8000 --udp-port 20777
```

看到类似 `Uvicorn running on http://0.0.0.0:8000` 就说明后端起来了。

> macOS 对照：`cd ~/f1-race-engineer && source .venv/bin/activate`，其余命令相同。
> 需要 AI 对话功能时，先设置 `ANTHROPIC_API_KEY`（见 §7）。

### 第二步：游戏内开启 UDP 遥测（Windows 上的 F1 25）

进入游戏 **Settings → Telemetry Settings**：

1. 打开 **UDP Telemetry**（On）。
2. **UDP Format 设为 `2026`**（关键！本项目只解析 2026 Season Pack 格式，选 2025 会全部校验失败）。
3. **UDP Port 填 `20777`**（必须与第一步 `--udp-port` 一致）。
4. 如有「服务器 IP / 广播」选项：**游戏和后端同一台电脑时填 `127.0.0.1`**；分机则填后端电脑的局域网 IP。

### 第三步：手机连接

1. 安装 App（见 §5）。
2. 打开 App → 底部「**设置**」页 → 填后端电脑的**局域网 IP** + 端口 `8000` → 点「**保存**」→「**测试连接**」。
3. 返回「仪表盘」页，游戏跑起来就能看到实时数据了。

---

## 3. 后端部署详解（Windows）

### 3.1 首次安装依赖

前置：安装 **Python 3.11+**（[python.org](https://www.python.org/downloads/) 下载，安装时勾选「Add python.exe to PATH」）。

```powershell
cd C:\你的路径\f1-race-engineer
python -m venv .venv          # 已存在可跳过
.venv\Scripts\activate
pip install -e .
```

> macOS 对照：`python3 -m venv .venv && source .venv/bin/activate && pip install -e .`

### 3.2 启动命令参数

```powershell
python scripts\serve.py `
  --db telemetry.sqlite3 `    # SQLite 库文件（数据都存在这里）
  --host 0.0.0.0 `            # 监听地址，0.0.0.0 = 所有网卡（默认，手机可连）
  --port 8000 `               # HTTP 端口（手机端也填这个）
  --udp-port 20777            # UDP 接收端口（游戏端填同一端口）
```

> 上面带 `（反引号）的行续写在 PowerShell 里用；CMD 下把反引号去掉写成一整行即可。

- **只读模式**（回放/演示历史数据）：不加 `--udp-port`，服务不监听 UDP，只对已入库数据提供仪表盘 + AI 对话。
- **实时模式**：加 `--udp-port`，额外启动 UDP 接收线程，把实时遥测落库并经 WebSocket 推给手机。

### 3.3 数据存在哪

所有遥测 + 分析结果都存进 `--db` 指定的 SQLite 文件（默认 `telemetry.sqlite3`，在项目目录下）。删掉这个文件即清空历史数据。

---

## 4. 游戏 UDP 端口说明

- **端口必须两端一致**：后端 `--udp-port` 填多少，游戏里 UDP Port 就填多少。
- 本项目**不硬编码默认端口**（官方 Spec 未给数值）。`20777` 是 F1 系列的历史惯例值，用它可以，用别的（如 `20779`）也行，只要两边对上。
- 游戏里 `UDP Format = 2026` 是**必须**的：项目只实现 2026 Season Pack 的遥测结构（29 字节 header），选 2025 legacy 格式会被校验层判定为失败（属预期，不是 bug）。
- **游戏和后端同机**：游戏里 UDP 服务器地址填 `127.0.0.1` 即可（走本机回环，无需防火墙放行 UDP）。

---

## 5. 手机端安装与更新

### 5.1 首次安装

- 方式一：下载已发布的 APK —— [GitHub Release v1.0.0](https://github.com/harries233/f1-race-engineer/releases/tag/v1.0.0) 里的 `F1-Race-Engineer.apk`，传到手机安装。
- 方式二：自己构建（见仓库根 `build-apk.sh`，需 Android Studio / Gradle）。
- Android 首次安装未知来源 App 时，系统会要求「允许安装未知应用」，按提示开启即可。

### 5.2 自动更新（OTA）

App 启动时会**静默检查**新版本（`update.json` 多镜像链，中国网络友好）。有新版本弹窗提示 → 点「更新」→ 自动多镜像回退下载 → 跳系统安装界面。

> 从旧 debug 版（0.1.0）升级到正式签名版（1.0.0）时，签名不一致，需先**卸载旧版**再装正式版。

---

## 6. 功能页使用说明

App 底部四个页签：

### 🏎️ 仪表盘（实时）
- WebSocket 实时推送：**速度 / 挡位 / 转速 / 油门 / 刹车**。
- 当前**会话**信息（赛道、天气、圈数等）。
- **圈速** Canvas 折线（历史圈速趋势）。
- **扇区 / 弯角** 数据卡片。

### 📊 对比（Setup 对比 / 推荐 / 实验）
- **对比**：两次调校（Setup）的圈速差异（delta 秒数，负 = 更快）。
- **推荐**：AI 基于你的遥测给出的 Setup 调整建议（每个参数都附理由 + 证据来源 + 置信度）。
- **实验**：A/B 验证记录（baseline vs test 的判定结果）。

### 🤖 AI（对话）
- 与 AI 车组工程师多轮对话，问「哪个弯最慢」「上一圈怎么改进」等。
- AI 只通过 Tool 层读后端算好的数据，不自己算数、不碰 UDP。

### ⚙️ 设置
- **后端连接**：主机 IP + 端口（默认 8000），保存后测连接。
- 关于：说明 + 数据来源等级徽标约定。

---

## 7. AI 对话配置（可选）

AI 对话走 Anthropic Claude，需要 API Key：

```powershell
# 启动后端前设置环境变量（PowerShell）
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python scripts\serve.py --db telemetry.sqlite3 --port 8000 --udp-port 20777
```

不设置也能用：除「AI」页对话外，其余功能（仪表盘/对比/实验）都是本地确定性计算，不依赖 API。

> 持久化设置（PowerShell）：`[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")`，重开终端生效。

---

## 8. 常见问题（FAQ）

**Q：手机连不上后端？**
1. 确认手机和电脑在**同一局域网**（同一个 WiFi / 路由器）。
2. 后端启动时确认用了 `--host 0.0.0.0`（默认就是）。
3. 手机填的是电脑的**局域网 IPv4** 不是公网 IP。查 IP：
   - Windows：`ipconfig`，看「无线局域网适配器 WLAN」下的 **IPv4 地址**（形如 `192.168.x.x`）。
   - macOS：`ipconfig getifaddr en0`。
4. **Windows 防火墙**：首次运行 Python 监听端口时，若弹「Windows 安全中心警报」，点**允许访问**；或手动放行 8000（TCP，入站）。游戏与后端同机走 `127.0.0.1` 不受此影响。

**Q：游戏在跑，但仪表盘没数据？**
1. 游戏里 UDP Telemetry 开了没、`UDP Format` 是不是 `2026`。
2. 游戏 UDP Port 和后端 `--udp-port` 是否一致。
3. 后端是否加了 `--udp-port`（漏了就是只读模式，不监听 UDP）。
4. 游戏与后端分机时，确认游戏填的是后端电脑 IP，且防火墙放行该 UDP 端口。

**Q：仪表盘有数据，但 AI 对话报错？**
- 没设置 `ANTHROPIC_API_KEY`，或 Key 无效/欠费。

**Q：数据可信吗？**
- 每个值都带来源徽标：`RAW`=游戏直发实测，`DERIVED`=本地公式计算，`HYPOTHESIS`=推测/占位（如部分赛道弯角边界为均匀等分，待真实数据标定）。看徽标就知道该信多少。

**Q：想清空数据重来？**
- 停后端（Ctrl+C），删除项目目录下的 `telemetry.sqlite3`，重新启动即可。

**Q：`python` 不是内部或外部命令？**
- Python 没装或没加 PATH。重装时勾选「Add python.exe to PATH」，或用 `py` 命令（Windows 自带启动器）替代 `python`。

---

## 9. 附：项目结构速览

```
f1-race-engineer/
├── src/ingest/        # UDP 接收
├── src/validate/      # 校验
├── src/store/         # SQLite 存储
├── src/protocol/      # 2026 Season Pack 协议解析
├── src/analysis/      # 圈速/扇区/逐弯/对比/推荐（确定性计算）
├── src/tools/         # AI 工具层
├── src/agent/         # AI 调度 + Claude 接入
├── src/server/        # FastAPI REST + WebSocket 服务
├── src/track/         # 赛道数据层（上海等）
├── scripts/serve.py   # 后端启动入口
├── android/           # 手机端（Kotlin + Jetpack Compose）
├── update.json        # OTA 更新清单
└── docs/architecture.md  # 架构与数据契约（开发者文档）
```

详细技术文档见 [architecture.md](architecture.md)；发布流程见仓库根 [RELEASE.md](../RELEASE.md)。
