# 任务报告：修复 Docker 编排失败 (Fix Orchestration Failure)

## 1. 任务摘要 (Summary)
解决在 1Panel 面板部署时出现的 `unknown docker command` 错误。经分析，该错误主要由编排名称包含**空格** (`TG ONE`) 造成，导致面板内部的 Docker 命令参数解析异常。解决方案为重命名编排除去空格。

---

## 2. 问题分析 (Diagnosis)

### 2.1 错误日志
```
2026/02/02 02:38:57 创建编排 [TG ONE] 任务开始 [START]
...
2026/02/02 02:38:58 unknown docker command: "compose ONE/docker-compose.yml"
```

### 2.2 根因 (Root Cause)
1Panel 面板在执行部署脚本时，可能采用类似以下的拼接逻辑：
```bash
docker compose -p ${project_name} -f ${project_dir}/docker-compose.yml up -d
```
当 `${project_name}` 为 `TG ONE` 时，虽然 Docker 官方 CLI 支持空格（若正确引用），但 1Panel 的内部处理或使用的 Shell 环境可能发生参数错位：
*   **现象**: `TG` 字符丢失或被误读，导致 `docker` 接收到的指令变成了 `compose ONE/docker-compose.yml` 这种畸形参数。

---

## 3. 解决方案 (Solution)

### ⚠️ 操作建议 (Action Required)

#### 方案 A: 1Panel 面板操作
1.  **重命名编排 (推荐)**:
    *   删除当前的 `TG ONE` 编排（保留数据卷）。
    *   重新创建编排，名称使用 **`TG_ONE`** 或 **`TG-ONE`** (无空格)。
    *   重新上传 `docker-compose.yml` 并部署。

#### 方案 B: 手动终端命令 (Manual CLI)
如果您通过 SSH 登录服务器，可以使用以下命令绕过面板限制：

**方法 1：直接运行（临时解决）**
```bash
# 1. 进入目录（需要加引号）
cd "TG ONE"

# 2. 强制指定无空格的项目名称并启动
docker compose -p tg_one up -d --build
```

**方法 2：彻底重命名（推荐，一劳永逸）**
```bash
# 1. 退出到上级目录并重命名文件夹
cd ~
mv "TG ONE" TG_ONE

# 2. 进入新目录没有任何空格烦恼
cd TG_ONE
docker compose up -d --build
```

---

## 4. 验证 (Verification)
*   **预期结果**: 修改名称后，1Panel 应能正确拼接路径，`docker compose` 命令顺利执行，服务正常启动。

## 5. 附录 (Appendix)
*   **Best Practice**: 在 Linux/Docker 运维环境中，文件、目录及任务名称应始终避免使用空格，推荐使用下划线 `_` 或连字符 `-`。
