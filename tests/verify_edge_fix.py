"""
Edge 浏览器性能修复验证脚本

用途：
1. 验证 psutil.cpu_percent 使用非阻塞模式
2. 验证 get_heartbeat 在线程池中执行
3. 检查 API 响应时间
"""

import asyncio
import time
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

async def test_cpu_percent_non_blocking():
    """测试 CPU 查询是否非阻塞"""
    print("\n[测试 1] 验证 psutil.cpu_percent 非阻塞模式")
    print("-" * 60)
    
    import psutil
    
    # 测试阻塞模式 (修复前)
    print("测试阻塞模式 (interval=0.1)...")
    start = time.time()
    cpu_blocking = psutil.cpu_percent(interval=0.1)
    elapsed_blocking = time.time() - start
    print(f"  结果: {cpu_blocking}%")
    print(f"  耗时: {elapsed_blocking*1000:.2f}ms")
    
    # 测试非阻塞模式 (修复后)
    print("\n测试非阻塞模式 (interval=None)...")
    start = time.time()
    cpu_non_blocking = psutil.cpu_percent(interval=None)
    elapsed_non_blocking = time.time() - start
    print(f"  结果: {cpu_non_blocking}%")
    print(f"  耗时: {elapsed_non_blocking*1000:.2f}ms")
    
    # 验证
    if elapsed_non_blocking < 0.01:  # 应小于 10ms
        print(f"\n✅ 通过: 非阻塞模式耗时 {elapsed_non_blocking*1000:.2f}ms < 10ms")
        return True
    else:
        print(f"\n❌ 失败: 非阻塞模式耗时 {elapsed_non_blocking*1000:.2f}ms >= 10ms")
        return False

async def test_api_response_time():
    """测试 API 响应时间"""
    print("\n[测试 2] 验证 API 响应时间")
    print("-" * 60)
    
    try:
        import aiohttp
        
        url = "http://localhost:8000/api/stats/system_resources"
        
        print(f"请求 URL: {url}")
        print("注意: 需要先启动 Web 服务器并登录")
        
        async with aiohttp.ClientSession() as session:
            start = time.time()
            async with session.get(url) as response:
                elapsed = time.time() - start
                data = await response.json()
                
                print(f"  状态码: {response.status}")
                print(f"  响应时间: {elapsed*1000:.2f}ms")
                
                if response.status == 200:
                    print(f"  CPU: {data.get('data', {}).get('cpu_percent', 'N/A')}%")
                    print(f"  内存: {data.get('data', {}).get('memory_percent', 'N/A')}%")
                
                if elapsed < 0.1:  # 应小于 100ms
                    print(f"\n✅ 通过: API 响应时间 {elapsed*1000:.2f}ms < 100ms")
                    return True
                else:
                    print(f"\n⚠️  警告: API 响应时间 {elapsed*1000:.2f}ms >= 100ms")
                    return False
                    
    except ImportError:
        print("⚠️  跳过: 需要安装 aiohttp (pip install aiohttp)")
        return None
    except Exception as e:
        print(f"❌ 失败: {e}")
        print("提示: 请确保 Web 服务器正在运行")
        return False

async def test_concurrent_requests():
    """测试并发请求是否互相阻塞"""
    print("\n[测试 3] 验证并发请求不互相阻塞")
    print("-" * 60)
    
    try:
        import aiohttp
        
        url = "http://localhost:8000/api/stats/system_resources"
        num_requests = 10
        
        print(f"发送 {num_requests} 个并发请求...")
        
        async with aiohttp.ClientSession() as session:
            start = time.time()
            
            tasks = [
                session.get(url)
                for _ in range(num_requests)
            ]
            
            responses = await asyncio.gather(*tasks, return_exceptions=True)
            elapsed = time.time() - start
            
            success_count = sum(1 for r in responses if not isinstance(r, Exception))
            
            print(f"  成功: {success_count}/{num_requests}")
            print(f"  总耗时: {elapsed*1000:.2f}ms")
            print(f"  平均耗时: {elapsed*1000/num_requests:.2f}ms")
            
            # 如果是阻塞的，10 个请求应该耗时 10 * 100ms = 1000ms
            # 如果是非阻塞的，应该接近单个请求的时间
            if elapsed < 0.5:  # 应小于 500ms
                print(f"\n✅ 通过: 并发请求总耗时 {elapsed*1000:.2f}ms < 500ms")
                return True
            else:
                print(f"\n❌ 失败: 并发请求总耗时 {elapsed*1000:.2f}ms >= 500ms")
                print("提示: 可能存在阻塞调用")
                return False
                
    except ImportError:
        print("⚠️  跳过: 需要安装 aiohttp (pip install aiohttp)")
        return None
    except Exception as e:
        print(f"❌ 失败: {e}")
        return False

async def verify_code_changes():
    """验证代码修改是否正确"""
    print("\n[测试 4] 验证代码修改")
    print("-" * 60)
    
    stats_router_path = "web_admin/routers/stats_router.py"
    
    if not os.path.exists(stats_router_path):
        print(f"❌ 失败: 找不到文件 {stats_router_path}")
        return False
    
    with open(stats_router_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 检查修复 1: psutil.cpu_percent(interval=None)
    if 'psutil.cpu_percent(interval=None)' in content:
        print("✅ 修复 1: psutil.cpu_percent 使用非阻塞模式")
    else:
        print("❌ 修复 1: 未找到 psutil.cpu_percent(interval=None)")
        return False
    
    # 检查修复 2: run_in_threadpool(get_heartbeat)
    if 'run_in_threadpool(get_heartbeat)' in content:
        print("✅ 修复 2: get_heartbeat 在线程池中执行")
    else:
        print("❌ 修复 2: 未找到 run_in_threadpool(get_heartbeat)")
        return False
    
    print("\n✅ 通过: 所有代码修改已正确应用")
    return True

async def main():
    """主测试函数"""
    print("=" * 60)
    print("Edge 浏览器性能修复验证")
    print("=" * 60)
    
    results = []
    
    # 测试 1: CPU 查询非阻塞
    results.append(await test_cpu_percent_non_blocking())
    
    # 测试 4: 代码修改验证
    results.append(await verify_code_changes())
    
    # 测试 2: API 响应时间 (需要服务器运行)
    result = await test_api_response_time()
    if result is not None:
        results.append(result)
    
    # 测试 3: 并发请求 (需要服务器运行)
    result = await test_concurrent_requests()
    if result is not None:
        results.append(result)
    
    # 总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = sum(1 for r in results if r is True)
    failed = sum(1 for r in results if r is False)
    total = len(results)
    
    print(f"通过: {passed}/{total}")
    print(f"失败: {failed}/{total}")
    
    if failed == 0:
        print("\n🎉 所有测试通过！修复已成功应用。")
        print("\n下一步:")
        print("1. 重启 Web 服务器")
        print("2. 在 Edge 浏览器中访问仪表板")
        print("3. 验证滚轮操作是否流畅")
        print("4. 检查 WebSocket 连接是否稳定")
    else:
        print("\n⚠️  部分测试失败，请检查修复是否正确应用。")
    
    return failed == 0

if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
