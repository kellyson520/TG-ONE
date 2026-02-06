import unittest
import logging
import time
import os
import shutil
from pathlib import Path
from core.logging import BufferedRotatingFileHandler

class TestLoggingOptimization(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("tests/temp/logging_test")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir, ignore_errors=True)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.test_dir / "test_buffer_fresh.log"
        self.handlers_to_close = []
        
    def tearDown(self):
        for h in self.handlers_to_close:
            try:
                h.close()
            except: pass
        if self.test_dir.exists():
            try:
                shutil.rmtree(self.test_dir, ignore_errors=True)
            except: pass

    def test_buffer_logic(self):
        print("\nStarting test_buffer_logic...")
        handler = BufferedRotatingFileHandler(
            filename=str(self.log_file),
            buffer_size=10,
            flush_interval=1.0
        )
        self.handlers_to_close.append(handler)
        
        # 使用随机名称避免冲突
        import uuid
        logger = logging.getLogger(f"test_buffer_{uuid.uuid4().hex[:6]}")
        logger.handlers = []
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False # 禁止传向 root

        # 1. 写入 5 条日志 (未达 buffer_size)
        print("Writing first 5 messages...")
        for i in range(5):
            logger.info(f"Buffered Message {i}")
        
        # 验证文件是否仍为空
        time.sleep(0.1)
        size = os.path.getsize(self.log_file) if self.log_file.exists() else 0
        print(f"File size after 5 messages: {size}")
        self.assertEqual(size, 0)

        # 2. 写入接下来的 5 条日志 (总计 10 条，触发 buffer_size)
        print("Writing next 5 messages (total 10)...")
        for i in range(5, 10):
            logger.info(f"Buffered Message {i}")
        
        # 给一点点磁盘 I/O 时间
        time.sleep(0.2)
        size_after = os.path.getsize(self.log_file) if self.log_file.exists() else 0
        print(f"File size after 10 messages: {size_after}")
        self.assertTrue(size_after > 0)
        
        # 3. 验证 ERROR 级立即落盘
        print("Testing immediate ERROR log...")
        error_log = self.test_dir / "error_test.log"
        err_handler = BufferedRotatingFileHandler(filename=str(error_log), buffer_size=100)
        self.handlers_to_close.append(err_handler)
        
        err_logger = logging.getLogger(f"test_error_{uuid.uuid4().hex[:6]}")
        err_logger.handlers = []
        err_logger.addHandler(err_handler)
        err_logger.propagate = False
        
        err_logger.error("Immediate Error Message")
        time.sleep(0.1)
        err_size = os.path.getsize(error_log) if error_log.exists() else 0
        print(f"Error log size: {err_size}")
        self.assertTrue(err_size > 0)

if __name__ == "__main__":
    unittest.main()
