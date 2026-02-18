# TimeFlow 开发技术路线图 (Technical Roadmap)

## 1. 项目愿景与架构概览 (Vision & Architecture)

**目标**: 构建一款"极简、高颜、稳定"的 Android 个人效能管理应用。
**核心原则**: Offline-First (离线优先), Esthetics First (颜值正义), Battery Friendly (省电).

### 架构分层 (Layered Architecture)

```
[Presentation Layer] (UI/UX)
   |-- Screens: Dashboard, TaskDetail, Pomodoro, Settings
   |-- Components: TimerCircle, TaskCard, GlassButton
   |-- Theme: Dark Mode, HSL Color Palette, Animations (Reanimated)

[State Management Layer]
   |-- Context/Zustand: Global Store (UserPrefs, ActiveTasks, TimerState)

[Service Layer] (Business Logic)
   |-- TimerEngine: Background Timer Calculation (Date.now delta)
   |-- NotificationManager: Local Push Scheduling
   |-- DailyResetService: "New Day" Detection & Task Reset

[Persistence Layer]
   |-- StorageAdapter: Async Storage Wrapper (JSON serialization)
   |-- Schema: Task { id, title, isDaily, completedAt, ... }
```

---

## 2. 技术选型详情 (Tech Stack Deep Dive)

| 模块 | 选型 | 理由 |
| :--- | :--- | :--- |
| **Core Framework** | **React Native (Expo)** | 跨平台标准，EAS Build 免环境配置，快速迭代。 |
| **Language** | **TypeScript** | 强类型约束，不仅防 Bug，更是为了自动补全和文档化。 |
| **Univeral UI** | **Tamagui** 或 **Gluestack UI** | 比 RN Paper 更现代，性能更好，支持复杂的动画和样式复用。推荐 Tamagui 用于构建"玻璃拟态"高端感。 |
| **Navigation** | **Expo Router (File-based)** | 类似 Next.js 的文件路由，结构更清晰，Deep Link 开箱即用。 |
| **State** | **Zustand** | 极简 Redux 替代品，无样板代码，不仅管理状态，还能轻松持久化。 |
| **Storage** | **MMKV** (可选) 或 **AsyncStorage** | 如果追求极致性能用 MMKV，普通应用 AsyncStorage 足够。 |
| **Animation** | **React Native Reanimated 3** | 必须使用。实现 60fps 的流畅微交互（如番茄钟倒计时圆环）。 |

---

## 3. 核心功能实现路径 (Implementation Path)

### 3.1 每日自动刷新 (The "Lazy" Reset Pattern)
不使用后台服务，而是采用**惰性求值**。
*   **Trigger**: App `AppState` 变为 `active` 时。
*   **Logic**:
    ```typescript
    const checkDailyReset = async () => {
      const today = getTodayString(); // "2023-10-27"
      const lastOpen = await storage.getString('last_open_date');
      if (lastOpen !== today) {
        await resetDailyTasks();
        await storage.set('last_open_date', today);
      }
    }
    ```

### 3.2 坚如磐石的计时器 (Bulletproof Timer)
*   **核心痛点**: `setInterval` 在后台会被挂起。
*   **解决方案**: **时间戳差值法**。
    *   开始时记录: `targetTime = now() + 25min`.
    *   UI 渲染: `remaining = targetTime - now()`.
    *   后台/前台切换: 重新计算 `remaining`，UI 会瞬间跳到正确时间，无缝衔接。

### 3.3 本地通知系统 (Notification System)
*   利用 `expo-notifications`。
*   **关键策略**:
    *   番茄钟开始时 -> 立即注册一个 25 分钟后的通知。
    *   用户若提前取消/完成 -> 立即取消该 Pending Notification。
    *   **权限**: Android 13+ 需要动态申请 Post Notification 权限。

---

## 4. 软著申请准备 (Software Copyright Ready)
为满足"拥有 15 年经验"的专业度，代码结构需严格模块化，以便提取文档。

*   **目录结构规范**:
    ```
    /src
      /components    # UI 组件 (用于软著"界面设计"章节)
      /core          # 核心算法 (用于软著"核心逻辑"章节)
        /timer.ts
        /scheduler.ts
      /hooks         # 业务逻辑钩子
      /app           # 路由页面
    ```
*   **文档生成**: 使用 TypeDoc 自动生成 API 文档，直接作为技术说明书的附件。

---

## 5. 开发环境与起步 (Getting Started)

### Step 1: 初始化
```powershell
# 强制使用最新稳定版 Expo
npx create-expo-app@latest TimeFlow --template blank-typescript
cd TimeFlow
npx expo install expo-router react-native-safe-area-context react-native-screens expo-linking expo-constants expo-status-bar
```

### Step 2: 安装核心库
```powershell
npx expo install @react-native-async-storage/async-storage expo-notifications expo-keep-awake
npm install zustand date-fns
```

### Step 3: 启动
```powershell
npx expo start
# 手机安装 "Expo Go" 扫描二维码即可预览
```

---

## 6. 下一步建议 (Next Steps)
1.  **确认 UI 风格**: 是否偏向深色模式？(Dark Mode)
2.  **原型开发**: 先把计时器跑通 (Console log 输出即可)，再做界面。
3.  **CI/CD**: 配置 Github Actions 自动运行 EAS Build (后续)。
