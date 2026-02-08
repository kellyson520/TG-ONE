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
# 使用缓存挂载加速 apt
# 2. 从官方镜像获取 uv (锁定版本以确保构建稳定性)
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv

# 3. 创建虚拟环境
RUN uv venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 4. 安装 Python 依赖 (使用清华源加速)
# 使用缓存挂载加速 uv
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install -r requirements.txt --index-url https://pypi.tuna.tsinghua.edu.cn/simple

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

# 从构建阶段复制虚拟环境
COPY --from=builder /opt/venv /opt/venv

# 确保运行时拥有 uv (从官方镜像复制，锁定版本)
COPY --from=ghcr.io/astral-sh/uv:0.10.0 /uv /usr/local/bin/uv

# 创建必要目录
RUN mkdir -p /app/temp /app/sessions /app/logs

# 复制项目代码
COPY . .

# 赋予脚本执行权限 (作为双重保险)
RUN chmod +x /app/scripts/ops/entrypoint.sh

# 启动命令
# 关键修复：使用 bash 显式执行脚本，绕过文件系统的执行权限限制
CMD ["bash", "/app/scripts/ops/entrypoint.sh"]