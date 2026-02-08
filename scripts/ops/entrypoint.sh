#!/bin/bash
# ==========================================
# TG ONE 工业级 Supervisor 守护进程
# 版本: 3.1 (Visual Enhancement)
# ==========================================
echo -e "\033[1;36m
   _______   _____     ____    _   __   ______
  /_  __/ | / /   |   / __ \  / | / /  / ____/
   / / /  |/ / /| |  / / / / /  |/ /  / __/   
  / / / /|  / ___ | / /_/ / / /|  /  / /___   
 /_/ /_/ |_/_/  |_| \____/ /_/ |_/  /_____/   
\033[0m"


# 定义常量
APP_DIR="/app"
DATA_DIR="$APP_DIR/data"
BACKUP_DIR="$DATA_DIR/backups/auto_update"
LOCK_FILE="$DATA_DIR/UPDATE_LOCK.json"
VERIFY_LOCK="$DATA_DIR/UPDATE_VERIFYING.json"
EXIT_CODE_UPDATE=10  # 约定：Python返回10代表请求系统级更新
BACKUP_LIMIT=10      # 保留备份数量

# 确保目录存在
mkdir -p "$BACKUP_DIR"

cd "$APP_DIR" || exit 1

# --- 函数：备份清理 (Rotation) ---
prune_backups() {
    local dir="$1"
    local pattern="$2"
    local limit="$3"
    
    # 查找符合模式的文件数量
    local count=$(ls -1 $dir/$pattern 2>/dev/null | wc -l)
    
    if [ "$count" -gt "$limit" ]; then
        echo "🧹 [守护进程] 正在清理旧备份 (保留最新 $limit 个)..."
        # 按时间排序，获取超出的部分并删除
        ls -t $dir/$pattern | tail -n +$((limit + 1)) | xargs rm -f
    fi
}

# --- 函数：依赖安装重试逻辑 ---
install_with_retry() {
    local max_retries=3
    local count=0
    
    echo "📦 [守护进程] 发现环境变更，开始同步依赖..."
    
    while [ $count -lt $max_retries ]; do
        # 使用 uv pip sync 强制对齐依赖 (自动安装缺失、卸载多余)
        # 注意: 在 Docker 环境中，uv 需要明确指定 python 环境或 --system
        echo "🔄 [守护进程] 执行 uv pip sync (Try $((count + 1))/$max_retries)..."
        
        uv pip sync requirements.txt --python $(which python3)
        
        if [ $? -eq 0 ]; then
            echo "✅ [守护进程] 依赖同步完成 (uv sync)。"
            return 0
        fi
        
        count=$((count + 1))
        echo "⚠️ [守护进程] 依赖同步失败，3秒后重试..."
        sleep 3
    done
    
    echo "❌ [守护进程] 依赖同步在 $max_retries 次尝试后彻底失败，尝试启动应用..."
    return 1
}

# --- 函数：智能依赖检查与修复 ---
check_and_fix_dependencies() {
    if [ ! -f "requirements.txt" ]; then
        return 0
    fi

    # 1. 快速检查：Python 级深度校验 (pkg_resources 是事实标准)
    echo "🔍 [守护进程] 正在校验 Python 依赖环境..."
    python3 -c "
import sys
import pkg_resources
from pkg_resources import parse_requirements

try:
    with open('requirements.txt') as f:
        reqs = [str(r) for r in parse_requirements(f.read())]
        pkg_resources.require(reqs)
    sys.exit(0)
except Exception as e:
    print(f'[DependencyCheck] Missing/Mismatch: {e}')
    sys.exit(1)
" 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "✅ [守护进程] 依赖环境校验通过。"
        return 0
    fi

    # 2. 只有检查失败时，才执行安装逻辑
    echo "🔧 [守护进程] 检测到 Python 依赖缺失或版本不匹配，触发热修复..."
    install_with_retry
    return $?
}

# --- 函数：执行回滚 ---
perform_rollback() {
    echo "🚨 [守护进程] 启动回滚程序..."
    
    # 查找可能的锁文件
    local current_lock=""
    if [ -f "$LOCK_FILE" ]; then current_lock="$LOCK_FILE"; fi
    if [ -f "$VERIFY_LOCK" ]; then current_lock="$VERIFY_LOCK"; fi

    # 优先尝试从 git 回滚（如果记录了前一个 SHA）
    if [ -n "$current_lock" ]; then
        PREV_SHA=$(python3 -c "import json; print(json.load(open('$current_lock')).get('prev_version', ''))" 2>/dev/null)
        if [ -n "$PREV_SHA" ]; then
            echo "⏪ [守护进程] 正在执行 Git 分支回滚至: $PREV_SHA"
            git reset --hard "$PREV_SHA"
            if [ $? -eq 0 ]; then
                echo "✅ [守护进程] Git 回滚成功。"
                rm -f "$LOCK_FILE" "$VERIFY_LOCK"
                return 0
            fi
        fi
    fi

    # Fallback: 从物理备份还原
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/code_backup_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        echo "☠️ [守护进程] 严重错误：未找到物理备份文件！系统可能已损坏。"
        return 1
    fi
    
    echo "⏪ [守护进程] 正在从备份恢复核心文件: $LATEST_BACKUP"
    # 还原时保留 data 目录
    tar -xzf "$LATEST_BACKUP" -C "$APP_DIR"
    
    if [ $? -eq 0 ]; then
        echo "✅ [守护进程] 物理回滚成功。"
        echo "{\"status\": \"rolled_back\", \"error\": \"启动持续失败，已触发紧急物理回滚\", \"timestamp\": \"$(date -u +%H:%M:%S)\"}" > "$DATA_DIR/update_state.json"
        rm -f "$LOCK_FILE" "$VERIFY_LOCK"
        # 回滚后恢复依赖（以防万一）
        check_and_fix_dependencies
    else
        echo "☠️ [守护进程] 物理回滚失败！"
        return 1
    fi
}

# --- 函数：执行更新 ---
perform_update() {
    echo "🔄 [守护进程] 接管系统更新流程..."
    
    # 0. 检查是否是手动回滚请求
    if [ -f "$LOCK_FILE" ]; then
        local STATUS=$(python3 -c "import json; print(json.load(open('$LOCK_FILE')).get('status', ''))" 2>/dev/null)
        if [ "$STATUS" == "rollback_requested" ]; then
            echo "⏪ [守护进程] 检测到手动回滚请求，正在跳过更新，直接执行回滚..."
            perform_rollback
            return
        fi
    fi
    
    # 1. 备份 (创建前清理超限备份)
    prune_backups "$BACKUP_DIR" "code_backup_*.tar.gz" "$BACKUP_LIMIT"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/code_backup_$TIMESTAMP.tar.gz"
    
    # 记录前一个版本 SHA 用于回滚
    PREV_SHA=$(git rev-parse HEAD 2>/dev/null)
    
    echo "📦 [守护进程] 创建当前版本快照: $BACKUP_PATH"
    tar --exclude='./data' --exclude='./.git' --exclude='./__pycache__' --exclude='./logs' --exclude='./temp' --exclude='./sessions' -czf "$BACKUP_PATH" . 2>/dev/null
    
    # 2. 拉取代码
    TARGET_VERSION="origin/main"
    if [ -f "$LOCK_FILE" ]; then
        TARGET_VERSION=$(python3 -c "import json; print(json.load(open('$LOCK_FILE')).get('version', 'origin/main'))" 2>/dev/null || echo "origin/main")
        # 将 PREV_SHA 注入锁文件
        python3 -c "import json; d=json.load(open('$LOCK_FILE')); d['prev_version']='${PREV_SHA}'; json.dump(d, open('$LOCK_FILE', 'w'))" 2>/dev/null
    fi
    
    echo "⬇️ [守护进程] 同步代码至分支/提交: $TARGET_VERSION"
    git fetch origin && git reset --hard "$TARGET_VERSION"
    
    if [ $? -ne 0 ]; then
        echo "❌ [守护进程] Git 拉取失败，系统未受损，取消本次更新。"
        rm -f "$LOCK_FILE"
        return
    fi
    
    echo "✅ [守护进程] 代码更新完成。"
}

# --- 初始化设置 ---
echo "🚀 [守护进程] TG ONE 守护进程启动 (v3.0)"

# 内存优化
JEMALLOC_PATH=""
if [ -f "/usr/lib/libjemalloc.so.2" ]; then
    JEMALLOC_PATH="/usr/lib/libjemalloc.so.2"
elif [ -f "/usr/lib/x86_64-linux-gnu/libjemalloc.so.2" ]; then
    JEMALLOC_PATH="/usr/lib/x86_64-linux-gnu/libjemalloc.so.2"
fi

if [ -n "$JEMALLOC_PATH" ]; then
    export LD_PRELOAD="$JEMALLOC_PATH"
    export MALLOC_CONF="background_thread:true,metadata_thp:auto,dirty_decay_ms:30000,muzzy_decay_ms:30000"
    echo "✅ [守护进程] 内存优化已启用: Jemalloc"
fi

export PYTHONDONTWRITEBYTECODE=1
export PYTHONUNBUFFERED=1

# --- 主循环 (Process Loop) ---
UPTIME_THRESHOLD=15  # 启动成功的最小运行秒数

while true; do
    # 核心增强：每次启动进程前先行验证环境，支持热补丁
    check_and_fix_dependencies

    echo "🚀 [守护进程] 正在启动 Python 主程序..."
    
    START_TIME=$(date +%s)
    
    # 启动 Python 主程序
    python3 -u main.py
    
    # 捕获退出码和运行时间
    EXIT_CODE=$?
    END_TIME=$(date +%s)
    UPTIME=$((END_TIME - START_TIME))
    
    echo "🛑 [守护进程] 应用已退出，退出码: $EXIT_CODE (运行时间: ${UPTIME}s)"
    
    # 判断退出原因
    if [ $EXIT_CODE -eq $EXIT_CODE_UPDATE ]; then
        perform_update
        echo "🔄 [守护进程] 更新请求已处理，3 秒后重启..."
        sleep 3
    else
        # 异常退出处理
        if [ -f "$LOCK_FILE" ] || [ -f "$VERIFY_LOCK" ]; then
            # 如果存在锁文件，说明这是更新后的尝试启动
            if [ $UPTIME -lt $UPTIME_THRESHOLD ]; then
                echo "⚠️ [守护进程] 检测到更新后启动失败 (Uptime: ${UPTIME}s < ${UPTIME_THRESHOLD}s)，准备回滚..."
                perform_rollback
                rm -f "$VERIFY_LOCK"
            else
                echo "⚠️ [守护进程] 更新后的运行时间通过阈值，清理更新标记..."
                rm -f "$LOCK_FILE"
                rm -f "$VERIFY_LOCK"
            fi
        fi
        
        if [ $EXIT_CODE -ne 0 ]; then
            echo "🔥 [守护进程] 检测到异常崩溃，冷却 5 秒..."
            sleep 5
        elif [ $EXIT_CODE -eq 0 ]; then
            echo "👋 [守护进程] 正常关闭信号。"
            exit 0
        fi
    fi
done

