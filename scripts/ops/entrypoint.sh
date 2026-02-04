#!/bin/bash
# ==========================================
# TG ONE 工业级 Supervisor 守护进程
# 版本: 2.0 (Industrial-Grade Auto-Update)
# ==========================================

# 定义常量
APP_DIR="/app"
DATA_DIR="$APP_DIR/data"
BACKUP_DIR="$DATA_DIR/backups/auto_update"
LOCK_FILE="$DATA_DIR/UPDATE_LOCK.json"
EXIT_CODE_UPDATE=10  # 约定：Python返回10代表请求系统级更新

# 确保目录存在
mkdir -p "$BACKUP_DIR"

cd "$APP_DIR" || exit 1

# --- 函数：执行回滚 ---
perform_rollback() {
    echo "🚨 [守护进程] 更新失败，正在启动回滚..."
    
    # 查找最新的代码备份
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/code_backup_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        echo "☠️ [守护进程] 严重错误：未找到备份文件！系统可能已损坏。"
        return
    fi
    
    echo "⏪ [守护进程] 正在从备份恢复: $LATEST_BACKUP"
    # 解压备份覆盖当前目录 (排除 data 目录以免覆盖用户数据)
    tar -xzf "$LATEST_BACKUP" -C "$APP_DIR"
    
    if [ $? -eq 0 ]; then
        echo "✅ [守护进程] 回滚成功。"
        # 记录失败状态供 Python 读取并通知
        echo "{\"status\": \"shell_failed\", \"error\": \"基础设施更新阶段失败（Git/Pip），已自动回滚\", \"timestamp\": \"$(date -u +%H:%M:%S)\"}" > "$DATA_DIR/update_state.json"
        # 删除锁文件，允许旧版本正常启动
        rm -f "$LOCK_FILE"
    else
        echo "☠️ [守护进程] 回滚失败！"
        echo "{\"status\": \"critical_failed\", \"error\": \"代码回滚彻底失败，系统处于不一致状态\", \"timestamp\": \"$(date -u +%H:%M:%S)\"}" > "$DATA_DIR/update_state.json"
    fi
}

# --- 函数：执行更新 ---
perform_update() {
    echo "🔄 [守护进程] 接管系统更新流程..."
    
    # 1. 创建代码级备份 (防 Git 失败)
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/code_backup_$TIMESTAMP.tar.gz"
    echo "📦 [守护进程] 正在创建代码备份: $BACKUP_PATH"
    # 排除 .git, data, __pycache__ 等
    tar --exclude='./data' --exclude='./.git' --exclude='./__pycache__' --exclude='./logs' --exclude='./temp' --exclude='./sessions' -czf "$BACKUP_PATH" . 2>/dev/null
    
    # 2. 获取目标版本 (从锁文件读取，默认 origin/main)
    TARGET_VERSION="origin/main"
    if [ -f "$LOCK_FILE" ]; then
        TARGET_VERSION=$(python3 -c "import json; print(json.load(open('$LOCK_FILE')).get('version', 'origin/main'))" 2>/dev/null || echo "origin/main")
    fi
    
    # 记录更新前的依赖哈希
    REQ_HASH_BEFORE=$(md5sum requirements.txt 2>/dev/null || echo "none")
    
    echo "⬇️ [守护进程] 正在同步代码至: $TARGET_VERSION"
    git fetch origin && git reset --hard "$TARGET_VERSION"
    
    if [ $? -ne 0 ]; then
        echo "❌ [守护进程] Git 拉取失败。"
        perform_rollback
        return
    fi
    
    # 3. 执行依赖安装 (仅在 requirements.txt 变化时)
    echo "📦 [守护进程] 正在检查 Python 依赖..."
    
    # 获取更新后的依赖哈希
    REQ_HASH_AFTER=$(md5sum requirements.txt 2>/dev/null || echo "none")
    
    if [ "$REQ_HASH_BEFORE" != "$REQ_HASH_AFTER" ]; then
        echo "📦 [守护进程] 检测到依赖变更，开始更新..."
        pip install --no-cache-dir -r requirements.txt
        
        if [ $? -ne 0 ]; then
            echo "❌ [守护进程] Pip 安装失败。"
            perform_rollback
            return
        fi
    else
        echo "✅ [守护进程] 依赖未发生变化，跳过安装。"
    fi
    
    echo "✅ [守护进程] 基础设施更新完成，交还控制权给 Python..."
}

# --- 一次性初始化 (仅首次启动执行) ---
echo "🚀 [守护进程] TG ONE 工业级守护进程正在启动..."

# 1. 内存优化 (Jemalloc)
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
    export MALLOC_CONF="background_thread:true,metadata_thp:auto,dirty_decay_ms:30000,muzzy_decay_ms:30000"
    echo "✅ [守护进程] 内存优化已启用: Jemalloc"
fi

# 2. Python 环境预调优
export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# 3. 初始健康检查
echo "🔍 [守护进程] 正在执行初始健康检查..."
if [ -f "scripts/ops/database_health_check.py" ]; then
    python3 scripts/ops/database_health_check.py || echo "⚠️ [守护进程] 数据库健康检查失败（非致命）"
fi

# --- 主循环 (死循环保活) ---
while true; do
    echo "🚀 [守护进程] 正在启动 TG ONE 应用..."
    
    # 启动 Python 主程序
    python3 -u main.py
    
    # 捕获退出码
    EXIT_CODE=$?
    
    echo "🛑 [守护进程] 应用已退出，退出码: $EXIT_CODE"
    
    # 判断退出原因
    if [ $EXIT_CODE -eq $EXIT_CODE_UPDATE ]; then
        # 情况A: Python 请求更新
        perform_update
        echo "🔄 [守护进程] 3 秒后重启..."
        sleep 3
    else
        # 情况B: 异常崩溃或正常退出
        if [ -f "$LOCK_FILE" ]; then
            echo "⚠️ [守护进程] 检测到更新状态下的崩溃！"
            # 如果锁文件存在且不是 Exit 10，说明是更新后的第一次启动崩溃了
            # 或者更新中途容器重启了，尝试再次执行更新确保环境正确
            perform_update
        fi
        
        if [ $EXIT_CODE -ne 0 ]; then
            echo "🔥 [守护进程] 检测到崩溃，冷却中（5秒）..."
            sleep 5
        else
            echo "👋 [守护进程] 正常关闭。"
            exit 0
        fi
    fi
done
