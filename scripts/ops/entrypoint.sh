#!/bin/bash
set -e

# ==========================================
# TG ONE 系统统一启动入口 (Entrypoint)
# ==========================================

echo "🚀 [$(date '+%Y-%m-%d %H:%M:%S')] 正在启动 TG ONE 转发系统..."

# 1. 内存优化 (Jemalloc)
# ------------------------------------------
# 自动探测 Jemalloc 路径 (兼容 Debian/Ubuntu/Alpine)
JEMALLOC_PATH=""
if [ -f "/usr/lib/libjemalloc.so.2" ]; then
    JEMALLOC_PATH="/usr/lib/libjemalloc.so.2"
elif [ -f "/usr/lib/x86_64-linux-gnu/libjemalloc.so.2" ]; then
    JEMALLOC_PATH="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"
elif [ -f "/usr/lib/aarch64-linux-gnu/libjemalloc.so.2" ]; then
    JEMALLOC_PATH="/usr/lib/aarch64-linux-gnu/libjemalloc.so.2"
fi

if [ -n "$JEMALLOC_PATH" ]; then
    export LD_PRELOAD="$JEMALLOC_PATH"
    # 针对低内存占用和后台线程进行调优
    export MALLOC_CONF="background_thread:true,metadata_thp:auto,dirty_decay_ms:30000,muzzy_decay_ms:30000"
    echo "✅ 内存优化已启用: Jemalloc ($JEMALLOC_PATH)"
else
    echo "⚠️  未发现 Jemalloc，将使用系统默认内存分配器。"
fi

# 2. Python 环境预调优
# ------------------------------------------
# 禁止生成 pyc 文件，确保输出实时刷新
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# 2.1 自动同步环境依赖
# ------------------------------------------
echo "📦 [$(date '+%Y-%m-%d %H:%M:%S')] 正在检查环境依赖..."
python3 scripts/ops/sync_dependencies.py

# 3. 数据库健康检查
# ------------------------------------------
echo "🔍 [$(date '+%Y-%m-%d %H:%M:%S')] 正在执行数据库健康检查..."
if python3 scripts/ops/database_health_check.py; then
    echo "✅ 数据库状态健康。"
else
    echo "❌ 数据库检查发现异常，正在尝试自动修复..."
    if python3 scripts/ops/fix_database.py; then
        echo "✅ 数据库修复成功。"
    else
        echo "❌ 数据库修复失败。请查看 logs/ 目录下的详细日志，程序退出。"
        exit 1
    fi
fi

# 4. 启动主程序
# ------------------------------------------
echo "🚀 [$(date '+%Y-%m-%d %H:%M:%S')] 正在进入运行循环..."
# 使用 exec 确保主程序能正确接收容器停止信号 (SIGTERM)
exec python3 -u main.py
