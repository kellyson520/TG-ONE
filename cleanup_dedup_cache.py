"""
清理持久化缓存中的去重数据
用于修复后清除旧的污染数据
"""
import asyncio
import sys
sys.path.insert(0, '.')

async def cleanup_dedup_pcache():
    """清理持久化缓存中的去重数据"""
    try:
        from core.cache.persistent_cache import get_persistent_cache
        
        pc = get_persistent_cache()
        
        print("=" * 60)
        print("清理去重持久化缓存")
        print("=" * 60)
        
        # 获取所有key (如果支持的话)
        print("\n正在扫描缓存中的去重key...")
        
        # 尝试使用不同的方法获取key
        keys_to_delete = []
        
        try:
            # 方法1: 如果是Redis,使用SCAN
            if hasattr(pc, 'scan_iter'):
                for key in pc.scan_iter(match="dedup:*"):
                    keys_to_delete.append(key)
            # 方法2: 如果是dict-like,使用keys()
            elif hasattr(pc, 'keys'):
                all_keys = pc.keys()
                keys_to_delete = [k for k in all_keys if k.startswith('dedup:')]
            else:
                print("⚠️  无法自动扫描key,请手动清理")
                print("   建议: 重启应用程序,持久化缓存会自动过期")
                return
        except Exception as e:
            print(f"⚠️  扫描key失败: {e}")
            print("   建议: 重启应用程序,持久化缓存会自动过期")
            return
        
        if not keys_to_delete:
            print("✅ 未找到需要清理的去重缓存key")
            return
        
        print(f"\n找到 {len(keys_to_delete)} 个去重缓存key")
        print("示例key:")
        for key in keys_to_delete[:5]:
            print(f"  - {key}")
        if len(keys_to_delete) > 5:
            print(f"  ... 还有 {len(keys_to_delete) - 5} 个")
        
        # 确认删除
        print("\n⚠️  警告: 这将删除所有去重缓存数据")
        print("   删除后,系统将重新学习去重规则")
        response = input("\n是否继续? (yes/no): ").strip().lower()
        
        if response != 'yes':
            print("❌ 已取消清理")
            return
        
        # 执行删除
        print("\n正在删除...")
        deleted_count = 0
        for key in keys_to_delete:
            try:
                pc.delete(key)
                deleted_count += 1
            except Exception as e:
                print(f"⚠️  删除失败: {key} - {e}")
        
        print(f"\n✅ 成功删除 {deleted_count}/{len(keys_to_delete)} 个key")
        print("\n建议:")
        print("1. 重启应用程序")
        print("2. 观察去重日志,确认不再误判")
        print("3. 监控系统性能,确保去重功能正常")
        
    except ImportError as e:
        print(f"❌ 导入失败: {e}")
        print("   请确保在项目根目录运行此脚本")
    except Exception as e:
        print(f"❌ 清理失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("\n提示: 如果持久化缓存使用Redis,请确保Redis服务正在运行")
    print("     如果使用文件缓存,请确保有写权限\n")
    
    try:
        asyncio.run(cleanup_dedup_pcache())
    except KeyboardInterrupt:
        print("\n\n❌ 用户中断")
    except Exception as e:
        print(f"\n❌ 执行失败: {e}")
        import traceback
        traceback.print_exc()
