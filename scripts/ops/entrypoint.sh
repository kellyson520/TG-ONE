#!/bin/bash
# ==========================================
# TG ONE 工业级 Supervisor 守护进程
# 版本: 3.0 (Industrial Evolution - Heavy Duty)
# ==========================================

# 定义常量
APP_DIR="/app"
DATA_DIR="$APP_DIR/data"
BACKUP_DIR="$DATA_DIR/backups/auto_update"
LOCK_FILE="$DATA_DIR/UPDATE_LOCK.json"
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
        # 1. 尝试安装
        pip install --no-cache-dir -r requirements.txt
        
        if [ $? -eq 0 ]; then
            # 2. 严格对齐：卸载不在清单中的包
            echo "🧹 [守护进程] 正在执行严格依赖对齐 (卸载无关包)..."
            python3 -c "
import json, subprocess, sys
try:
    with open('requirements.txt') as f:
        reqs = {line.split('#')[0].split(';')[0].split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].split('!=')[0].split('[')[0].strip().lower().replace('_', '-') 
                for line in f if line.strip() and not line.startswith('#')}
    res = subprocess.run([sys.executable, '-m', 'pip', 'list', '--format=json'], capture_output=True, text=True)
    if res.returncode == 0:
        installed = {p['name'].lower().replace('_', '-') for p in json.loads(res.stdout)}
        protected = {'pip', 'setuptools', 'wheel', 'pip-tools', 'distribute', 'certifi', 'pkg-resources'}
        to_remove = installed - reqs - protected
        if to_remove:
            print(f'[DependencyGuard] Removing extraneous: {to_remove}')
            subprocess.run([sys.executable, '-m', 'pip', 'uninstall', '-y'] + list(to_remove))
except Exception as e:
    print(f'[DependencyGuard] Alignment error: {e}')
"
            echo "✅ [守护进程] 依赖同步完成。"
            return 0
        fi
        
        count=$((count + 1))
        echo "⚠️ [守护进程] 依赖安装失败 (尝试 $count/$max_retries)，3秒后重试..."
        sleep 3
    done
    
    echo "❌ [守护进程] 依赖安装在 $max_retries 次尝试后彻底失败，尝试启动应用..."
    return 1
}

# --- 函数：智能依赖检查与修复 ---
check_and_fix_dependencies() {
    if [ ! -f "requirements.txt" ]; then
        return 0
    fi

    # 1. 快速检查：Python 级深度校验 (pkg_resources 是事实标准)
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
        return 0
    fi

    # 2. 只有检查失败时，才执行安装逻辑
    echo "🔧 [守护进程] 检测到 Python 依赖缺失或版本不匹配，触发热修复..."
    install_with_retry
    return $?
}

# --- 函数：执行回滚 ---
perform_rollback() {
    echo "🚨 [守护进程] 更新失败，正在启动回滚..."
    LATEST_BACKUP=$(ls -t "$BACKUP_DIR"/code_backup_*.tar.gz 2>/dev/null | head -1)
    
    if [ -z "$LATEST_BACKUP" ]; then
        echo "☠️ [守护进程] 严重错误：未找到备份文件！系统可能已损坏。"
        return
    fi
    
    echo "⏪ [守护进程] 正在从备份恢复: $LATEST_BACKUP"
    tar -xzf "$LATEST_BACKUP" -C "$APP_DIR"
    
    if [ $? -eq 0 ]; then
        echo "✅ [守护进程] 回滚成功。"
        echo "{\"status\": \"shell_failed\", \"error\": \"基础设施更新阶段失败，已自动回滚\", \"timestamp\": \"$(date -u +%H:%M:%S)\"}" > "$DATA_DIR/update_state.json"
        rm -f "$LOCK_FILE"
        # 回滚后恢复依赖
        install_with_retry
    else
        echo "☠️ [守护进程] 回滚失败！"
    fi
}

# --- 函数：执行更新 ---
perform_update() {
    echo "🔄 [守护进程] 接管系统更新流程..."
    
    # 1. 备份 (创建前清理超限备份)
    prune_backups "$BACKUP_DIR" "code_backup_*.tar.gz" "$BACKUP_LIMIT"
    
    TIMESTAMP=$(date +%Y%m%d_%H%M%S)
    BACKUP_PATH="$BACKUP_DIR/code_backup_$TIMESTAMP.tar.gz"
    echo "📦 [守护进程] 创建备份: $BACKUP_PATH"
    tar --exclude='./data' --exclude='./.git' --exclude='./__pycache__' --exclude='./logs' --exclude='./temp' --exclude='./sessions' -czf "$BACKUP_PATH" . 2>/dev/null
    
    # 2. 拉取代码
    TARGET_VERSION="origin/main"
    if [ -f "$LOCK_FILE" ]; then
        TARGET_VERSION=$(python3 -c "import json; print(json.load(open('$LOCK_FILE')).get('version', 'origin/main'))" 2>/dev/null || echo "origin/main")
    fi
    
    echo "⬇️ [守护进程] 同步代码至: $TARGET_VERSION"
    git fetch origin && git reset --hard "$TARGET_VERSION"
    
    if [ $? -ne 0 ]; then
        echo "❌ [守护进程] Git 拉取失败。"
        perform_rollback
        return
    fi
    
    echo "✅ [守护进程] 代码更新完成，依赖检查将由下次循环自动处理。"
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
while true; do
    # 核心增强：每次启动进程前先行验证环境，支持热补丁
    check_and_fix_dependencies

    echo "🚀 [守护进程] 正在启动 Python 主程序..."
    
    # 启动 Python 主程序
    python3 -u main.py
    
    # 捕获退出码
    EXIT_CODE=$?
    
    echo "🛑 [守护进程] 应用已退出，退出码: $EXIT_CODE"
    
    # 判断退出原因
    if [ $EXIT_CODE -eq $EXIT_CODE_UPDATE ]; then
        perform_update
        echo "🔄 [守护进程] 3 秒后重启..."
        sleep 3
    else
        # 异常退出处理
        if [ -f "$LOCK_FILE" ]; then
            echo "⚠️ [守护进程] 更新后首次启动失败，尝试恢复..."
            perform_update
        fi
        
        if [ $EXIT_CODE -ne 0 ]; then
            echo "🔥 [守护进程] 检测到异常崩溃，冷却 5 秒..."
            sleep 5
        else
            echo "👋 [守护进程] 正常关闭。"
            exit 0
        fi
    fi
done

