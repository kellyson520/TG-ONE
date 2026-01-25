"""时间选择器按钮构造器"""

from telethon.tl.custom import Button


def build_numeric_picker_buttons(side: str, field: str, values: list[int], labels: list[str] | None = None,
                                 per_row: int = 6) -> list[list]:
    """根据给定的值和可选标签构建数字选择按钮矩阵。
    side: start|end, field: year|month|day|seconds
    values: 数值列表；labels 与 values 长度一致时使用 labels，否则自动渲染
    per_row: 每行显示数量
    """
    buttons: list[list] = []
    row: list = []
    for idx, v in enumerate(values):
        label = labels[idx] if labels and idx < len(labels) else str(v)
        row.append(Button.inline(label, f"new_menu:set_time_field:{side}:{field}:{v}"))
        if len(row) == per_row:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return buttons


