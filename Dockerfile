# syntax=docker/dockerfile:1
# ==========================================
# 第一阶段：构建阶段 (Builder)
# ==========================================
FROM python:3.11-slim AS builder

WORKDIR /app

# 设置环境变量，优化构建过程
ENV PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONUNBUFFERED=1

# 1. 安装编译依赖
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv

# 显示构建横幅 (Builder Stage) - 使用 Heredoc 解决截断问题
RUN <<EOF
echo -e "\033[1;36m+--------------------------------------------------+\033[0m"
echo -e "\033[1;36m|    _______   _____     ____    _   __   ______   |\033[0m"
echo -e "\033[1;36m|   /_  __/ | / /   |   / __ \  / | / /  / ____/   |\033[0m"
echo -e "\033[1;36m|    / / /  |/ / /| |  / / / / /  |/ /  / __/      |\033[0m"
echo -e "\033[1;36m|   / / / /|  / ___ | / /_/ / / /|  /  / /___      |\033[0m"
echo -e "\033[1;36m|  /_/ /_/ |_/_/  |_| \____/ /_/ |_/  /_____/      |\033[0m"
echo -e "\033[1;36m+--------------------------------------------------+\033[0m"
echo -e "\033[1;32m  🚀 [BUILD] TG ONE - Initiating Infrastructure...\033[0m"
EOF

# 3. 创建虚拟环境
RUN echo "\033[1;34m🛠️  [BUILD] Creating Virtual Environment...\033[0m" && \
    uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 4. 安装 Python 依赖 (使用清华源加速)
# 使用缓存挂载加速 uv
# 显式设置 UV_LINK_MODE=copy 以消除 Docker 缓存层无法硬链接的警告
ENV UV_LINK_MODE=copy

COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    echo "\033[1;34m📦 [BUILD] Installing Dependencies via uv...\033[0m" && \
    uv pip install -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
    echo "\033[1;32m✅ [BUILD] Dependencies Installed Successfully.\033[0m"

# ==========================================
# 第二阶段：运行阶段 (Runtime)
# ==========================================
FROM python:3.11-slim

WORKDIR /app

# 设置基础环境变量
ENV PYTHONUNBUFFERED=1 \
    DOCKER_LOG_MAX_SIZE=10m \
    DOCKER_LOG_MAX_FILE=3 \
    PATH="/opt/venv/bin:$PATH"

# 4. 安装运行时系统依赖
# 注意：先安装依赖，再设置 LD_PRELOAD，消除构建时的 ld.so 报错
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y \
    tzdata \
    libjemalloc2 \
    curl \
    && ln -fs /usr/share/zoneinfo/Asia/Shanghai /etc/localtime \
    && dpkg-reconfigure -f noninteractive tzdata \
    && rm -rf /var/lib/apt/lists/*

# 5. Jemalloc 内存优化将由启动脚本动态配置

# 运行时横幅
RUN <<EOF
echo -e "\033[1;35m+--------------------------------------------------+\033[0m"
echo -e "\033[1;35m|  🛠️  [RUNTIME] Setting up Production Environment  |\033[0m"
echo -e "\033[1;35m+--------------------------------------------------+\033[0m"
EOF

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 确保运行时拥有 uv (从官方镜像复制，锁定版本)
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv

# 创建必要目录
RUN echo "\033[1;34m📂 [RUNTIME] Creating Directories...\033[0m" && \
    mkdir -p /app/data/temp /app/data/sessions /app/data/logs && \
    echo "\033[1;32m✅ [RUNTIME] Ready to Launch.\033[0m"

# 复制项目代码
COPY . .

# 赋予脚本执行权限 (作为双重保险)
RUN chmod +x /app/scripts/ops/entrypoint.sh

# 启动命令
# 关键修复：使用 bash 显式执行脚本，绕过文件系统的执行权限限制
ENV UV_LINK_MODE=copy
CMD ["bash", "/app/scripts/ops/entrypoint.sh"]