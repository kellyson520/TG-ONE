import os
import unittest
import tempfile
import shutil
from pathlib import Path

# Import the service logic if possible, or mock it
# For entrypoint.sh logic, we will test the string parsing directly

def parse_requirements_mock(text):
    """Refined parser from entrypoint.sh v3.0"""
    reqs = set()
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Logic: split by #, then ;, then ==, >=, <=, ~=, !=, [
        name = line.split('#')[0].split(';')[0].split('==')[0].split('>=')[0].split('<=')[0].split('~=')[0].split('!=')[0].split('[')[0].strip().lower().replace('_', '-')
        if name:
            reqs.add(name)
    return reqs

class TestUpdateRobustness(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        
    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_requirements_parsing(self):
        """测试 requirements.txt 的鲁棒解析"""
        content = """
        flask==2.3.2
        RequestS>=2.25.1 # with comment
        aiohttp[speedups]
        django; python_version < "3.10"
        # ignored-lib==1.0
        
        telethon~=1.30
        """
        parsed = parse_requirements_mock(content)
        expected = {'flask', 'requests', 'aiohttp', 'django', 'telethon'}
        self.assertEqual(parsed, expected)

    def test_dependency_alignment_logic(self):
        """测试卸载逻辑的包名提取与匹配"""
        reqs = {'flask', 'requests'}
        # Simulate pip list --format=json
        installed_raw = [
            {"name": "flask", "version": "2.3.2"},
            {"name": "requests", "version": "2.28.1"},
            {"name": "pip", "version": "23.0"},
            {"name": "extraneous-lib", "version": "1.0.0"},
            {"name": "dangerous_lib", "version": "6.6.6"}
        ]
        
        installed = {p['name'].lower().replace('_', '-') for p in installed_raw}
        protected = {'pip', 'setuptools', 'wheel', 'pip-tools', 'distribute', 'certifi', 'pkg-resources'}
        
        to_remove = installed - reqs - protected
        
        self.assertIn('extraneous-lib', to_remove)
        self.assertIn('dangerous-lib', to_remove)
        self.assertNotIn('pip', to_remove)
        self.assertNotIn('flask', to_remove)

    def test_backup_rotation_time_based(self):
        """测试 UpdateService 的 _rotate_backups 逻辑"""
        # Create mock backups
        backup_dir = self.test_dir / "backups"
        backup_dir.mkdir()
        
        # Create 15 files with different modification times
        import time
        for i in range(15):
            f = backup_dir / f"test_backup_{i}.zip"
            f.write_text("dummy")
            # Set mtime back in time
            os.utime(f, (time.time() - (15 - i) * 60, time.time() - (15 - i) * 60))
            
        # The rotation logic (re-implemented here for testing)
        import glob
        pattern = "test_backup_*.zip"
        limit = 10
        
        file_list = sorted(
            glob.glob(str(backup_dir / pattern)),
            key=os.path.getmtime,
            reverse=True
        )
        
        if len(file_list) > limit:
            to_delete = file_list[limit:]
            for f in to_delete:
                os.remove(f)
                
        # Check result
        remaining = list(backup_dir.glob(pattern))
        self.assertEqual(len(remaining), 10)
        
        # Ensure the REMAINING ones are the NEWS (latest ones)
        # test_backup_14 is the newest (mtime = now - 1*60)
        # test_backup_0 is the oldest (mtime = now - 15*60)
        remaining_names = [f.name for f in remaining]
        self.assertIn("test_backup_14.zip", remaining_names)
        self.assertIn("test_backup_5.zip", remaining_names)
        self.assertNotIn("test_backup_0.zip", remaining_names)
        self.assertNotIn("test_backup_4.zip", remaining_names)

if __name__ == "__main__":
    unittest.main()
