#!/bin/bash
# F1 25 AI Race Engineer — Android 客户端构建脚本
# 用法: bash build-apk.sh            → debug 构建（默认）
#       bash build-apk.sh release    → release 构建（需 ~/.gradle/f1-re-release.properties）
#
# 前置：Android Studio（自带 JBR 21）+ Android SDK。本机 SDK 路径 ~/Library/Android/sdk。

set -e
cd "$(dirname "$0")"

MODE="${1:-debug}"

# 1. 定位 Java（Android Studio 内置 JBR 21）
if [ -z "$JAVA_HOME" ]; then
    if [ -d "/Applications/Android Studio.app/Contents/jbr/Contents/Home" ]; then
        export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"
    else
        export JAVA_HOME=$(/usr/libexec/java_home 2>/dev/null || echo "")
    fi
fi
echo "  JAVA_HOME: $JAVA_HOME"

# 2. 定位 Android SDK
if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
    if [ -d "$HOME/Library/Android/sdk" ]; then
        export ANDROID_HOME="$HOME/Library/Android/sdk"
    elif [ -d "$HOME/Android/Sdk" ]; then
        export ANDROID_HOME="$HOME/Android/Sdk"
    else
        echo "✗ 未找到 Android SDK（请安装 Android Studio 或设置 ANDROID_HOME）"
        exit 1
    fi
fi
echo "  SDK: $ANDROID_HOME"

# 3. 构建
cd android
if [ "$MODE" = "release" ] && [ -f "$HOME/.gradle/f1-re-release.properties" ]; then
    echo "  使用 release 签名构建…"
    ./gradlew assembleRelease
    TASK="assembleRelease"
else
    echo "  构建 debug APK…"
    ./gradlew assembleDebug
    TASK="assembleDebug"
fi

# 4. 定位产物
APK=$(find app/build/outputs/apk -name "*.apk" 2>/dev/null | head -1)
if [ -n "$APK" ]; then
    echo ""
    echo "✓ APK 生成：$APK"
else
    echo "  APK 在 android/app/build/outputs/apk/ 目录"
fi
