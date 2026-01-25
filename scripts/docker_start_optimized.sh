#!/bin/sh
# 优化版 Docker 启动脚本 - 高效内存管理

set -e  # 遇错即停

echo "🚀 [$(date '+%Y-%m-%d %H:%M:%S')] 启动 Telegram 转发器（优化模式）..."

# ==========================================
# 1. Jemalloc 内存优化配置
# ==========================================
echo "🔧 配置 Jemalloc 内存优化..."

# Alpine 下 jemalloc 路径
JEMALLOC_PATH="/usr/lib/libjemalloc.so.2"

if [ -f "$JEMALLOC_PATH" ]; then
    export LD_PRELOAD="$JEMALLOC_PATH"
    
    # Jemalloc 调优参数（降低内存碎片）
    export MALLOC_CONF="background_thread:true,metadata_thp:auto,dirty_decay_ms:30000,muzzy_decay_ms:30000"
    
    echo "✅ Jemalloc 已启用: $JEMALLOC_PATH"
    echo "   配置: $MALLOC_CONF"
else
    echo "⚠️  Jemalloc 未找到，使用系统默认内存分配器"
fi

# ==========================================
# 2. Python 内存优化
# ==========================================
# 限制 Python GC 阈值，减少频繁回收
export PYTHONMALLOC=malloc

# ==========================================
# 3. 数据库健康检查（快速失败）
# ==========================================
echo "🔍 [$(date '+%Y-%m-%d %H:%M:%S')] 数据库健康检查..."

if python3 scripts/database_health_check.py 2>&1 | tee /tmp/db_check.log; then
    echo "✅ 数据库检查通过"
else
    echo "❌ 数据库检查失败，尝试自动修复..."
    
    if python3 scripts/fix_database.py 2>&1 | tee /tmp/db_fix.log; then
        echo "✅ 数据库修复成功"
    else
        echo "❌ 数据库修复失败，详见日志："
        cat /tmp/db_fix.log
        exit 1
    fi
fi

# ==========================================
# 4. 预清理旧日志（可选，释放磁盘空间）
# ==========================================
echo "🧹 清理超过 7 天的旧日志..."
find /app/logs -name "*.log" -mtime +7 -delete 2>/dev/null || true

# ==========================================
# 5. 启动主程序（优雅处理信号）
# ==========================================
echo "🚀 [$(date '+%Y-%m-%d %H:%M:%S')] 启动主程序..."

# 使用 exec 替换当前进程，确保信号正确传递
exec python3 -u main.py
