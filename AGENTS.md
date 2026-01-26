
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
Check if any skill matches the user's request.
Action: view_file(AbsolutePath=".../SKILL.md") before proceeding.
</usage>

<available_skills>

  <skill>
    <name>api-contract-manager</name>
    <description>Intelligent bridge for Frontend-Backend data interoperability. Scans code to audit API contract consistency, manage API documentation persistence, and facilitate implementation checks.</description>
    <path>.agent/skills/api-contract-manager/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>architecture-auditor</name>
    <description>Architecture compliance auditor for TG ONE. Scans and enforces "Standard_Whitepaper.md" rules including Handler Purity, Lazy Execution, and Layering.</description>
    <path>.agent/skills/architecture-auditor/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>async-error-handling</name>
    <description>Expert guidance on Python async/await error handling patterns, context managers, and FastAPI lifecycle management</description>
    <path>.agent/skills/async-error-handling/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>database</name>
    <description>Expert database development, SQL optimization, and Schema management.</description>
    <path>.agent/skills/database/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>db-migration-enforcer</name>
    <description>自动化执行数据库架构演进检查，确保 SQLAlchemy 模型与数据库表结构同步。自动生成缺失的 ALTER TABLE 语句并维护 migrate_db 函数。</description>
    <path>.agent/skills/db-migration-enforcer/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>docs-archiver</name>
    <description>Automated archiving of completed tasks from active Workstreams.</description>
    <path>.agent/skills/docs-archiver/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>docs-maintenance</name>
    <description>Automated documentation synchronization and cleanliness maintenance.</description>
    <path>.agent/skills/docs-maintenance/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>encoding-fixer</name>
    <description>Detects and fixes file encoding issues (Mojibake, Non-UTF8, UTF-16LE in logs). Essential for Windows/Python cross-platform development.</description>
    <path>.agent/skills/encoding-fixer/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>full-system-verification</name>
    <description>Orchestrates comprehensive system testing including Unit, Integration, and Edge cases.</description>
    <path>.agent/skills/full-system-verification/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>git-manager</name>
    <description>Expert Git version control manager. Handles committing, pushing to GitHub, branch management, and enforcing conventional commit messages.</description>
    <path>.agent/skills/git-manager/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>python-runtime-diagnostics</name>
    <description>Expert diagnostics for Python runtime errors including ModuleNotFoundError, UnboundLocalError, and Import issues.</description>
    <path>.agent/skills/python-runtime-diagnostics/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>realtime-architect</name>
    <description>Standardized Full-Stack WebSocket Architecture for Real-time Systems</description>
    <path>.agent/skills/realtime-architect/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>skill-author</name>
    <description>Expert system for crafting Antigravity Skill definitions. Use this to create new skills or standardize existing ones according to the Meta-Prompt specifications.</description>
    <path>.agent/skills/skill-author/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>skill-evolution</name>
    <description>A meta-skill to create other skills. It analyzes repetitive tasks and scaffolds new skill definitions to enable system self-evolution.</description>
    <path>.agent/skills/skill-evolution/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>skill-master</name>
    <description>Intelligent skill orchestrator that automatically finds, creates, executes, and improves skills. When you need to accomplish a task, this skill searches for existing skills (internal, GitHub via MCP, web), creates new skills if none found, executes them, and reviews execution to improve skills based on actual usage. Also handles feedback about skill-generated outputs - if you want to fix/adjust an output AND improve the skill that created it, invoke this with your feedback. Use when you want automated skill discovery, continuous improvement, or to provide feedback on previous skill outputs.</description>
    <path>.agent/skills/skill-master/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>task-lifecycle-manager</name>
    <description>标准化任务生命周期管理，涵盖任务创建(Template)、进度同步(Sync)、文档规范(Spec/Report)及闭环归档(Finalize)。确保 PSB 协议的文档完整性与状态真实性。</description>
    <path>.agent/skills/task-lifecycle-manager/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>task-scanner</name>
    <description>Scans documentation for incomplete tasks in todo.md files to prevent dropped loops.</description>
    <path>.agent/skills/task-scanner/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>task-syncer</name>
    <description>Validates and synchronizes todo.md status with actual file system state. Ensures no "Hallucinated Progress".</description>
    <path>.agent/skills/task-syncer/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>telegram-bot</name>
    <description>High-performance Telegram Bot development using Telethon/Pyrogram.</description>
    <path>.agent/skills/telegram-bot/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>ui-ux-pro-max</name>
    <description>UI/UX design intelligence. 50 styles, 21 palettes, 50 font pairings, 20 charts, 9 stacks (React, Next.js, Vue, Svelte, SwiftUI, React Native, Flutter, Tailwind, shadcn/ui). Actions: plan, build, create, design, implement, review, fix, improve, optimize, enhance, refactor, check UI/UX code. Projects: website, landing page, dashboard, admin panel, e-commerce, SaaS, portfolio, blog, mobile app, .html, .tsx, .vue, .svelte. Elements: button, modal, navbar, sidebar, card, table, form, chart. Styles: glassmorphism, claymorphism, minimalism, brutalism, neumorphism, bento grid, dark mode, responsive, skeuomorphism, flat design. Topics: color palette, accessibility, animation, layout, typography, font pairing, spacing, hover, shadow, gradient. Integrations: shadcn/ui MCP for component search and examples.</description>
    <path>.agent/skills/ui-ux-pro-max/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>vercel-deploy</name>
    <description>Deploy applications and websites to Vercel. Use this skill when the user requests deployment actions such as "Deploy my app", "Deploy this to production", "Create a preview deployment", "Deploy and give me the link", or "Push this live". No authentication required - returns preview URL and claimable deployment link.</description>
    <path>.agent/skills/vercel-deploy/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>windows-platform-adapter</name>
    <description>Expert knowledge for developing python applications on Windows/PowerShell environments. Handles shell differences, encoding issues, and file system quirks.</description>
    <path>.agent/skills/windows-platform-adapter/SKILL.md</path>
    <location>project</location>
  </skill>

  <skill>
    <name>workspace-hygiene</name>
    <description>强制执行项目工作空间整洁规范，防止临时测试文件污染根目录。提供根目录扫描、违规文件自动迁移至 tests/temp/ 或 docs/CurrentTask/ 的功能。</description>
    <path>.agent/skills/workspace-hygiene/SKILL.md</path>
    <location>project</location>
  </skill>

</available_skills>
<!-- SKILLS_TABLE_END -->

</skills_system>
