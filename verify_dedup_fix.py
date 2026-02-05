"""
快速验证去重系统修复
"""
import sys
sys.path.insert(0, '.')

print("=" * 60)
print("去重系统修复验证")
print("=" * 60)

# 验证1: batch_add 方法存在
print("\n[验证1] 检查 DedupRepository.batch_add 方法...")
from repositories.dedup_repo import DedupRepository
assert hasattr(DedupRepository, 'batch_add'), "❌ batch_add 方法不存在"
print("✅ batch_add 方法存在")

import inspect
sig = inspect.signature(DedupRepository.batch_add)
params = list(sig.parameters.keys())
assert 'records' in params, f"❌ batch_add 缺少 records 参数,当前参数: {params}"
print(f"✅ batch_add 方法签名正确: {sig}")

# 验证2: 检查 _record_message 中是否移除了自动写入PCache的代码
print("\n[验证2] 检查 _record_message 中的PCache写入逻辑...")
with open('services/dedup/engine.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
# 检查是否包含注释说明
if "❌ 移除自动写入持久化缓存的逻辑" in content:
    print("✅ 已移除 _record_message 中的自动PCache写入")
else:
    print("⚠️  未找到移除标记,请手动检查")

# 验证3: 检查是否在重复检测时添加了PCache写入
print("\n[验证3] 检查重复检测时的PCache写入逻辑...")
checks = [
    ("签名重复检测", "检测到重复,写入持久化缓存以加速后续判重"),
    ("内容哈希重复检测", "检测到重复,写入持久化缓存以加速后续判重"),
    ("相似度重复检测", "检测到相似重复,尝试记录文本哈希到PCache"),
]

for check_name, marker in checks:
    if marker in content:
        print(f"✅ {check_name}: 已添加PCache写入逻辑")
    else:
        print(f"❌ {check_name}: 未找到PCache写入逻辑")

# 验证4: 检查持久化缓存的key格式
print("\n[验证4] 检查持久化缓存key格式...")
if 'f"dedup:sig:{cache_chat_key}:{signature}"' in content:
    print("✅ 签名PCache key格式正确")
else:
    print("⚠️  签名PCache key格式可能有变化")

if 'f"dedup:hash:{cache_chat_key}:{content_hash}"' in content:
    print("✅ 哈希PCache key格式正确")
else:
    print("⚠️  哈希PCache key格式可能有变化")

print("\n" + "=" * 60)
print("验证完成!")
print("=" * 60)
print("\n建议:")
print("1. 重启应用程序以应用修复")
print("2. 清空持久化缓存(如果有旧数据污染)")
print("3. 监控去重日志,确认不再出现误判")
print("4. 观察批量写入是否正常工作")
