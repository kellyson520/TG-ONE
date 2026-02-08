# Setup Guide

## Prerequisites
- Python 3.11+
- uv (Fast Python package installer)

## Installing uv

### Windows
```powershell
pip install uv==0.10.0
```

### Linux/macOS
```bash
# 安装指定版本
curl -LsSf https://astral.sh/uv/0.10.0/install.sh | sh
```

## Installing Dependencies

```bash
uv pip install -r requirements.txt
```

## Docker Build

The Dockerfile has been updated to use `uv` automatically.

```bash
docker-compose build
```
