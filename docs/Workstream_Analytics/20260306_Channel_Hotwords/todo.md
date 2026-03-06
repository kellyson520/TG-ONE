# Channel Hotwords Analysis (频道热词分析)

## 背景 (Context)
实现全频道的聊天文本内容实时检测与热词分析。基于分词与词频（TF-IDF或纯词频加权）算法，提取各个频道的每日、每月、每年以及汇总热词。提供指令 `/hot 频道名` 进行精确检索，并支持系统每天定时推送全局总频道日榜。

## 待办清单 (Checklist)

### Phase 1: 架构设计与基础设施 (Architecture & Infrastructure)
- [ ] 编写详细技术方案 (`spec.md`) 并与用户确认。
- [ ] 检查并引入分词库（如 `jieba`）。
- [ ] 定义存储目录结构 (`data/hot/...`) 与文件管理规范。
- [ ] 在 `core.config` 中增加热词统计的相关配置项（功能开关、推送目标等）。

### Phase 2: 核心采集与分析链路 (Collection & Analysis Pipeline)
- [ ] 创建 `HotwordExtractorMiddleware` 接入 `Pipeline`，实时非阻塞收集文本。
- [ ] 实现 `HotwordService`: 管理热词的分析、加权计算和缓冲落盘（写入 `temp.json`）。
- [ ] 复用 `WorkerService` / 异步调度框架实现 `temp` 到 `day` 的定期自动滚动和增量计算。

### Phase 3: 自动化折叠与聚合 (Scheduling & Aggregation)
- [ ] 编写定时任务守护进程 (或复用现有系统)：在每天 00:00 生成上一日的报表，创建/更新对应的 `day` 文件。
- [ ] 在每月 1 日，将所有 `day` 文件归纳合并生成上一月的 `month` 文件。
- [ ] 在次年 1 月 1 日，将对应 `month` 归纳为 `year` 文件，以及维护持续累加的 `all.json`。

### Phase 4: UI 与指令集成 (UI & Commands)
- [ ] 编写 `/hot <频道名>` 指令的解析 Handler。
- [ ] 编写 `/hot` (无参数返回总频道或选项菜单) 的交互查询。
- [ ] 实现每日总榜推送服务 `sender_service` 的对接，每日固定时间把全局热词推送到指定管理群/频道。
