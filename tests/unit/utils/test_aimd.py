import unittest
from services.network.aimd import AIMDScheduler

class TestAIMDScheduler(unittest.TestCase):
    def setUp(self):
        self.scheduler = AIMDScheduler(
            min_interval=60,
            max_interval=3600,
            multiplier=0.5,
            increment=60
        )
        self.scheduler.current_interval = 600

    def test_increase_on_no_content(self):
        """测试无内容时线性增加 (Additive Increase)"""
        # 600 + 60 = 660
        new_val = self.scheduler.update(found_new_content=False)
        self.assertEqual(new_val, 660)
        self.assertEqual(self.scheduler.current_interval, 660)
        
        # 660 + 60 = 720
        new_val = self.scheduler.update(found_new_content=False)
        self.assertEqual(new_val, 720)

    def test_decrease_on_new_content(self):
        """测试有内容时乘性减少 (Multiplicative Decrease)"""
        self.scheduler.current_interval = 1000
        
        # 1000 * 0.5 = 500
        new_val = self.scheduler.update(found_new_content=True)
        self.assertEqual(new_val, 500)
        
        # 500 * 0.5 = 250
        new_val = self.scheduler.update(found_new_content=True)
        self.assertEqual(new_val, 250)

    def test_bounds(self):
        """测试最小/最大边界"""
        # 测试最大值
        self.scheduler.current_interval = 3580
        new_val = self.scheduler.update(found_new_content=False)
        self.assertEqual(new_val, 3600) # Cap at 3600
        
        new_val = self.scheduler.update(found_new_content=False)
        self.assertEqual(new_val, 3600) # Still 3600

        # 测试最小值
        self.scheduler.current_interval = 100
        new_val = self.scheduler.update(found_new_content=True)
        self.assertEqual(new_val, 60) # 100 * 0.5 = 50 -> capped at 60

if __name__ == '__main__':
    unittest.main()
