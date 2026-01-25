#!/bin/bash
# Docker 启动脚本 - 包含数据库健康检查

echo "🚀 启动 Telegram 转发器..."

# 自动检测 jemalloc 路径 (兼容 x86_64 和 aarch64)
echo "🔍 检测 Jemalloc 路径..."
JEMALLOC_PATH=$(find /usr/lib -name libjemalloc.so.2 | head -n 1)

if [ -n "$JEMALLOC_PATH" ]; then
    export LD_PRELOAD="$JEMALLOC_PATH"
    echo "✅ Enabled Memory Optimization: $JEMALLOC_PATH"
else
    echo "⚠️ Jemalloc not found, skipping memory optimization."
fi

# 检查数据库健康状态
echo "🔍 检查数据库健康状态..."
if python3 scripts/database_health_check.py;
then
    echo "✅ 数据库检查通过"
else
    echo "❌ 数据库检查失败，尝试自动修复..."
    if python3 scripts/fix_database.py;
    then
        echo "✅ 数据库修复成功"
    else
        echo "❌ 数据库修复失败，请检查日志"
        exit 1
    fi
fi

# 启动主程序
echo "🚀 启动主程序..."
exec python3 main.py
