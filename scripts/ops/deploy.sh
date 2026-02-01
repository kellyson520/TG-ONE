#!/bin/bash
# ==========================================
# Telegram Forwarder 统一部署脚本
# 支持：标准部署 / 1Panel / 优化模式
# ==========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_error() { echo -e "${RED}❌ $1${NC}"; }

echo "=========================================="
echo "  🚀 Telegram Forwarder 部署脚本"
echo "=========================================="
echo ""

# 检查是否在项目根目录
if [ ! -f "docker-compose.yml" ]; then
    print_error "请在项目根目录运行此脚本"
    exit 1
fi

# 检测 docker-compose 命令（使用数组避免参数解析问题）
if command -v docker-compose &> /dev/null; then
    COMPOSE_CMD=(docker-compose)
elif docker compose version &> /dev/null; then
    COMPOSE_CMD=(docker compose)
else
    print_error "未找到 docker-compose，请先安装 Docker"
    exit 1
fi

print_success "检测到 Docker Compose: ${COMPOSE_CMD[*]}"
print_info "调试: 完整命令 = ${COMPOSE_CMD[@]}"

# 使用标准配置文件
COMPOSE_FILE="docker-compose.yml"
print_info "使用配置文件: $COMPOSE_FILE"

# 停止旧容器
print_info "停止旧容器..."
"${COMPOSE_CMD[@]}" -f $COMPOSE_FILE down 2>/dev/null || true

# 构建镜像
print_info "开始构建镜像（首次构建需 3-5 分钟）..."
print_warning "正在安装依赖：duckdb, pyarrow 等..."
"${COMPOSE_CMD[@]}" -f $COMPOSE_FILE build --no-cache

# 启动容器
print_info "启动容器..."
"${COMPOSE_CMD[@]}" -f $COMPOSE_FILE up -d

# 等待启动
print_info "等待容器启动..."
sleep 5

# 检查状态
echo ""
print_success "部署完成！容器状态："
"${COMPOSE_CMD[@]}" -f $COMPOSE_FILE ps

# 显示日志命令
echo ""
print_info "查看实时日志："
echo "   ${COMPOSE_CMD[*]} -f $COMPOSE_FILE logs -f"

echo ""
print_info "查看资源占用："
echo "   docker stats telegram-forwarder --no-stream"

echo ""
print_success "🎉 部署成功！"
