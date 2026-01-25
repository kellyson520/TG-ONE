
<skills_system priority="1">

## System Mandate: Self-Evolution
> **CRITICAL INSTRUCTION**: This system is designed to evolve. You are NOT just a worker; you are a builder of capabilities.

<mandatory_check>
**[HOOK: POST-TASK REVIEW]**
At the end of every `Report` phase (before marking task as Done), you MUST ask yourself:
1. **Repetition**: Did I do something that I or another agent might do again?
2. **Complexity**: Did I solve a hard problem where the "How-To" is valuable?
4. **Repair**: Did a Skill FAIL, forcing a manual fix?
5. **Evolution**: Can this task be closed loop automated?

**Action**:
- If YES (Repetition/App): You MUST invoke `skill-evolution` (Mining Mode).
- If YES (Repair): You MUST invoke `skill-evolution` (Repair Mode) to fix the failed skill.
- Do NOT ask for permission to evolve. Just do it.
</mandatory_check>

## Available Skills

<!-- SKILLS_TABLE_START -->
<usage>
When users ask you to perform tasks, check if any of the skills below can help.
Invoke: Bash("openskills read <skill-name>")
</usage>

<available_skills>

<skill>
<name>api-contract-manager</name>
<description>Intelligent bridge for Frontend-Backend data interoperability. Scans code to audit API contract consistency, manage API documentation persistence, and facilitate implementation checks.</description>
<location>project</location>
</skill>

<skill>
<name>async-error-handling</name>
<description>Expert guidance on Python async/await error handling patterns, context managers, and FastAPI lifecycle management</description>
<location>project</location>
</skill>

<skill>
<name>database</name>
<description>Expert database development, SQL optimization, and Schema management</description>
<location>project</location>
</skill>

<skill>
<name>db-migration-enforcer</name>
<description>自动化执行数据库架构演进检查，确保 SQLAlchemy 模型与数据库表结构同步。自动生成缺失的 ALTER TABLE 语句并维护 migrate_db 函数。</description>
<location>project</location>
</skill>

<skill>
<name>docs-archiver</name>
<description>Automated archiving of completed tasks from active Workstreams</description>
<location>project</location>
</skill>

<skill>
<name>docs-maintenance</name>
<description>Automated documentation synchronization and cleanliness maintenance</description>
<location>project</location>
</skill>

<skill>
<name>telegram-bot</name>
<description>High-performance Telegram Bot development using Telethon/Pyrogram</description>
<location>project</location>
</skill>

<skill>
<name>ui-ux-pro-max</name>
<description>UI/UX design intelligence. 50 styles, 21 palettes, 50 font pairings, 20 charts, 9 stacks (React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind, shadcn/ui). Actions: plan, build, create, design, implement, review, fix, improve, optimize, enhance, refactor, check UI/UX code. Projects: website, landing page, dashboard, admin panel, e-commerce, SaaS, portfolio, blog, mobile app, .html, .tsx, .vue, .svelte. Elements: button, modal, navbar, sidebar, card, table, form, chart. Styles: glassmorphism, claymorphism, minimalism, brutalism, neumorphism, bento grid, dark mode, responsive, skeuomorphism, flat design. Topics: color palette, accessibility, animation, layout, typography, font pairing, spacing, hover, shadow, gradient.</description>
<location>project</location>
</skill>

<skill>
<name>skill-evolution</name>
<description>Meta-skill to create new skills. Analyzes tasks and scaffolds automation.</description>
<location>project</location>
</skill>

<skill>
<name>skill-author</name>
<description>Expert system for crafting Antigravity Skill definitions. Use this to create new skills.</description>
<location>project</location>
</skill>

<skill>
<name>task-lifecycle-manager</name>
<description>Standardizes task lifecycle (Plan-Sync-Finalize) and ensures documentation integrity.</description>
<location>project</location>
</skill>

<skill>
<name>core-engineering</name>
<description>Core engineering standards, TDD flow, and architecture validation.</description>
<location>project</location>
</skill>

<skill>
<name>task-syncer</name>
<description>Validates and synchronizes todo.md status with actual file system state. Ensures no "Hallucinated Progress".</description>
<location>project</location>
</skill>

<skill>
<name>python-runtime-diagnostics</name>
<description>Expert diagnostics for Python runtime errors including ModuleNotFoundError, UnboundLocalError, and Import issues.</description>
<location>project</location>
</skill>

<skill>
<name>workspace-hygiene</name>
<description>强制执行项目工作空间整洁规范，防止临时测试文件污染根目录。提供根目录扫描、违规文件自动迁移至 tests/temp/ 或 docs/CurrentTask/ 的功能。</description>
<location>project</location>
</skill>

<skill>
<name>task-scanner</name>
<description>Scans documentation for incomplete tasks in todo.md files to prevent dropped loops.</description>
<location>project</location>
</skill>

<skill>
<name>full-system-verification</name>
<description>Orchestrates comprehensive system testing including Unit, Integration, and Edge cases.</description>
<location>project</location>
</skill>

<skill>
<name>api-contract-manager</name>
<description>Intelligent bridge for Frontend-Backend data interoperability. Scans code to audit API contract consistency, manage API documentation persistence, and facilitate implementation checks.</description>
<location>project</location>
</skill>


<skill>
<name>realtime-architect</name>
<description>Standardized Full-Stack WebSocket Architecture for Real-time Systems</description>
<location>project</location>
</skill>

</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>
