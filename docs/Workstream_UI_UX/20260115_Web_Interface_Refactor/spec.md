# Web 界面重构技术方案 (Web Interface Refactor Spec)

## 1. 核心设计语言 (Core Design System)

### 1.1 色彩方案 (Color Palette)
使用更温和、且具辨识度的色彩系统，减少强烈的渐变，增加层级感。

| Token | Light Mode (Default) | Dark Mode | Usage |
| :--- | :--- | :--- | :--- |
| `--bg-body` | `#F8FAFC` (Slate-50) | `#0F172A` (Slate-950) | 页面整体背景 |
| `--bg-card` | `rgba(255, 255, 255, 0.8)` | `rgba(30, 41, 59, 0.7)` | 卡片背景 (Glass) |
| `--primary` | `#6366F1` (Indigo-500) | `#818CF8` (Indigo-400) | 主色调/核心操作 |
| `--primary-hover`| `#4F46E5` | `#6366F1` | 主色悬浮 |
| `--text-main` | `#1E293B` (Slate-800) | `#F1F5F9` (Slate-100) | 正文文本 |
| `--text-muted` | `#64748B` (Slate-500) | `#94A3B8` (Slate-400) | 辅助/说明文本 |
| `--border` | `rgba(0, 0, 0, 0.05)` | `rgba(255, 255, 255, 0.1)` | 分隔线/边框 |
| `--shadow-sm` | `0 1px 2px rgba(0,0,0,0.05)`| `0 1px 2px rgba(0,0,0,0.2)` | 轻微阴影 |
| `--shadow-md` | `0 4px 6px -1px rgba(0,0,0,0.1)`| `0 4px 6px -1px rgba(0,0,0,0.3)` | 中度阴影 |

### 1.2 字体与排版 (Typography)
- **Primary Font**: `Inter`, `Segoe UI`, `-apple-system`, `system-ui`, `sans-serif`.
- **Size Scale**: 12px (Small), 14px (Base), 16px (Medium), 18px (Large), 24px (Title).
- **Line Height**: 1.5 for body text, 1.2 for headings.

### 1.3 间距与圆角 (Spacing & Radius)
- **Base Unit**: 4px (Gap-1: 4px, Gap-2: 8px, Gap-4: 16px, Gap-6: 24px).
- **Radius**: Large (12px) for cards, Medium (8px) for buttons/inputs, Small (4px) for inner tags.

## 2. 交互与动画 (Interactions & Animations)
- **Transition**: `200ms cubic-bezier(0.4, 0, 0.2, 1)`.
- **Hover Feedback**: 
  - Card: Subtle lift (`translateY(-2px)`) + subtle shadow deepening.
  - Button: Opacity change (0.9) or background shift.
- **Loading State**: Pulse animation for skeleton elements.

## 3. 核心布局改进 (Layout Improvements)
### 3.1 侧边栏 (Sidebar)
- 移除复杂的 JS 联动，改用纯 CSS 结构。
- 增加悬浮图标状态提示。
- 使用 `sticky` 定位替代部分 fixed 定位以提升滚动性能。

### 3.2 导航栏 (Navbar)
- 样式更加扁平化。
- 资源监控数据改为更简洁的标签，减少定时器频率 (10s)。

## 4. 性能优化策略 (Performance Strategy)
- **移除粒子背景**: 移除 Canvas 操作，释放 CPU/GPU。
- **减少层叠滤镜**: 仅在必要卡片上使用 `backdrop-filter`。
- **CSS 瘦身**: 剔除冗余的选择器，合并公共组件类。
- **图片优化**: 使用 Lucide/Bootstrap Icons 的 SVG 形式，避免大图。

## 5. 实施路线图 (Implementation Roadmap)
1. **P1 (样式注入)**: 更新 `:root` 变量并重写 `main.css` 的基础类。
2. **P2 (架构调整)**: 更新 `base.html` 删除 `<canvas>`，调整容器结构。
3. **P3 (组件更新)**: 更新仪表盘、规则列表的渲染模板。
