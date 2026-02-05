# 技术方案 (Spec) - 滚轮式时间选择器

## 1. UI 设计 (UI Design)

基于 Telegram Inline Keyboard 的限制，采用“三行滚动”模拟滚轮效果：

```
[ 2024年 ] [ 12月 ] [ 01日 ] [ 12时 ] [ 00分 ] [ 00秒 ]
[  ^  ] [  ^  ] [  ^  ] [  ^  ] [  ^  ] [  ^  ]
[  v  ] [  v  ] [  v  ] [  v  ] [  v  ] [  v  ]
[        ✅ 确定选择         ]
```
或者分步骤选择，但在同一个页面通过回调刷新：

### 滚轮式组件布局 (Wheel Layout):
- 第一行：当前选中的完整时间预览。
- 第二行：各单位的“上一个”选项（可选，或仅用箭头）。
- 第三行：各单位的“增加”箭头 `🔼`。
- 第四行：当前数值显示。
- 第五行：各单位的“减少”箭头 `🔽`。
- 第六行：功能按钮（返回、保存、不限）。

## 2. 逻辑设计 (Implementation Logic)

### 2.1 动态生成
- 年份：根据当前年份及用户会话最早时间动态生成范围。
- 月份：1-12。
- 日期：根据年月动态计算该月天数 (28-31)。
- 时分秒：0-23, 0-59。

### 2.2 回调指令 (Callback Tags)
- `new_menu:picker:step:{side}:{field}:{value}`
- `new_menu:picker:adjust:{side}:{field}:{delta}` (例如 delta=+1)

### 2.3 获取最早时间
- 从数据库中查询 `ForwardRule` 或 `Chat` 相关的最早记录。
- 或者默认从 2020 年开始，如果数据量大。
- *修正*: 优先尝试获取当前选定 Source Chat 的第一条消息时间。

## 3. API 变更 (API Changes)
- 无需变更现有 `SessionService` 接口，仅需扩展 `PickerMenu` 的渲染方法。
- `show_wheel_picker(event, side, current_values)`

## 4. 视觉要求 (Aesthetics)
- 使用 Emoji 增强反馈。
- 采用中文完整格式。
