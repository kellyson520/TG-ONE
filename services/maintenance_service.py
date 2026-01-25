import threading
import time
import pathlib
import psutil
import logging
from utils.helpers.tombstone import tombstone
from core.config import settings

logger = logging.getLogger(__name__)

class MaintenanceService:
    def __init__(self):
        # 从settings中获取临时文件清理阈值，默认5 GiB
        self.temp_guard_max = settings.TEMP_GUARD_MAX
        self.temp_guard_path = pathlib.Path('./temp')  # 与项目内 ./temp 同目录
        
        # 内存限制，默认500MB
        self.memory_limit_mb = 500
        
        # 停止事件
        self._stop_event = threading.Event()
        
        # 守护线程引用
        self._temp_guard_thread = None
        self._memory_guard_thread = None
        
        logger.info("MaintenanceService initialized")
    
    def start(self):
        """
        启动所有守护线程
        """
        logger.info("Starting maintenance services...")
        
        # 启动临时目录守护线程
        self._temp_guard_thread = threading.Thread(
            target=self._temp_guard_worker,
            daemon=True,
            name='TempGuard'
        )
        self._temp_guard_thread.start()
        logger.info("TempGuard thread started")
        
        # 启动内存守卫线程
        self._memory_guard_thread = threading.Thread(
            target=self._memory_guard_worker,
            daemon=True,
            name='MemGuard'
        )
        self._memory_guard_thread.start()
        logger.info("MemGuard thread started")
        
        logger.info("All maintenance services started")
    
    def stop(self):
        """
        停止所有守护线程
        """
        logger.info("Stopping maintenance services...")
        self._stop_event.set()
        
        # 等待线程结束
        if self._temp_guard_thread:
            self._temp_guard_thread.join(timeout=5.0)
            logger.info("TempGuard thread stopped")
        
        if self._memory_guard_thread:
            self._memory_guard_thread.join(timeout=5.0)
            logger.info("MemGuard thread stopped")
        
        logger.info("All maintenance services stopped")
    
    def _temp_guard_worker(self):
        """
        每1小时检查./temp目录，超过阈值时清理最旧文件
        """
        while not self._stop_event.is_set():
            try:
                if not self.temp_guard_path.exists():
                    time.sleep(3600)  # 1小时
                    continue
                
                # 1. 单次扫描获取所有文件信息
                files = []
                total_size = 0
                # 使用 scandir 通常比 rglob 更快
                for f in self.temp_guard_path.rglob('*'):
                    if f.is_file():
                        try:
                            stat = f.stat()
                            size = stat.st_size
                            total_size += size
                            # 保存 (修改时间, 大小, 路径)
                            files.append((stat.st_mtime, size, f))
                        except OSError:
                            pass
                
                logger.debug(f"[temp-guard] 当前临时目录大小: {total_size/1024/1024:.2f}MB, 最大限制: {self.temp_guard_max/1024/1024:.2f}MB, 文件数量: {len(files)}")
                
                # 2. 仅当超出限制时才进行排序和删除
                if total_size > self.temp_guard_max:
                    # 按时间升序排序（最旧的在前）
                    files.sort(key=lambda x: x[0])
                    
                    deleted_size = 0
                    target_size = total_size - self.temp_guard_max
                    deleted_count = 0
                    
                    for _, size, f in files:
                        if deleted_size >= target_size:
                            break
                        try:
                            if f.exists():
                                f.unlink()
                                deleted_size += size
                                deleted_count += 1
                                logger.debug(f"[temp-guard] 已清理缓存: {f.name} ({size/1024/1024:.2f}MB)")
                        except Exception as e:
                            logger.debug(f"[temp-guard] 清理文件失败: {f.name}, 错误: {str(e)}")
                            pass
                    
                    logger.info(f"[temp-guard] 清理完成: 删除 {deleted_count} 个文件, 释放 {deleted_size/1024/1024:.2f}MB 空间")
                            
            except Exception as e:
                logger.error(f"[temp-guard] 清理异常: {str(e)}")
            finally:
                # 确保每次循环后都有足够的休眠时间，避免频繁扫描
                time.sleep(3600)  # 1小时
    
    def _memory_guard_worker(self):
        """
        内存墓碑守卫：内存过高时冻结非活跃状态
        """
        while not self._stop_event.is_set():
            try:
                time.sleep(30)  # 每30秒检查一次
                
                # 增加 try-except 包裹 psutil 调用
                try:
                    process = psutil.Process()
                    mem_info = process.memory_info()
                    rss_mb = mem_info.rss / 1024 / 1024
                except Exception as e:
                    logger.error(f"[mem-guard] 获取内存信息失败: {str(e)}")
                    continue  # 获取内存失败就跳过本次

                # 如果内存超过阈值，且当前未冻结
                if rss_mb > self.memory_limit_mb and not tombstone._is_frozen:
                    # 在主事件循环中执行冻结操作（因为涉及 asyncio）
                    try:
                        import asyncio
                        # 获取当前运行的事件循环
                        current_loop = asyncio.get_event_loop()
                        asyncio.run_coroutine_threadsafe(tombstone.freeze(), current_loop)
                        logger.warning(f"[mem-guard] 内存使用过高 ({rss_mb:.2f}MB > {self.memory_limit_mb}MB)，已触发冻结")
                    except Exception as e:
                        logger.error(f"[mem-guard] 调用 tombstone.freeze() 失败: {e}")
                        
            except Exception as e:
                logger.error(f"[mem-guard] 异常: {e}")
                time.sleep(60)  # 出错后多睡一会
