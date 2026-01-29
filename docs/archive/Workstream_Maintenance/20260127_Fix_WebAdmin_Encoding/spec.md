# 技术方案: Mojibake 修复逻辑

## 问题分析
当前乱码属于“双重编码”问题。
1. 原始字符: `添加` (UTF8: `E6 B7 BB E5 8A A0`)
2. 错误读取: 将上述 6 字节按 GBK 解码。
   - `E6 B7` -> `娣`
   - `BB E5` -> `诲`
   - `8A A0` -> `姞`
3. 结果: `娣诲姞` (UTF8)

## 修复算法
要恢复原始字符，需要逆转上述过程：
1. 取出当前乱码字符串 (UTF8).
2. 编码为 GBK 字节流 (还原原始 UTF8 字节流).
3. 将得到的字节流按 UTF-8 解码 (还原原始字符).

```python
def fix_mojibake(bad_text: str) -> str:
    try:
        # 将 UTF-8 的乱码字符还原为原始字节（当时被当做 GBK 的字节）
        original_bytes = bad_text.encode('gbk')
        # 将这些原始字节重新按 UTF-8 解码
        corrected_text = original_bytes.decode('utf-8')
        return corrected_text
    except (UnicodeEncodeError, UnicodeDecodeError):
        # 如果转换失败，说明不是这种类型的乱码，返回原值
        return bad_text
```

## 实施计划
1. ** identify_mojibake.py**: 遍历文件，读取内容，检测是否包含特征字符。
2. ** repair_mojibake.py**: 读取受损文件，按行或整文件进行逻辑转换，写入新文件。
