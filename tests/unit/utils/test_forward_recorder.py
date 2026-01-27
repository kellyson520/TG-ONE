import pytest
import json
import os
from pathlib import Path
from unittest.mock import MagicMock
from datetime import datetime
from core.helpers.forward_recorder import ForwardRecorder

@pytest.fixture
def temp_recorder(tmp_path):
    # Initialize recorder with a temporary directory
    recorder = ForwardRecorder(base_dir=str(tmp_path))
    recorder.mode = "full" # Force full mode for testing file writes
    return recorder

def create_mock_message(msg_id=1, text="test", date=None, sender=None, chat=None, media=None):
    msg = MagicMock()
    msg.id = msg_id
    msg.message = text
    msg.date = date or datetime.utcnow()
    msg.sender = sender
    msg.chat = chat
    msg.media = media
    msg.forward = None
    msg.reply_to = None
    return msg

@pytest.mark.asyncio
class TestForwardRecorder:
    async def test_record_forward_success(self, temp_recorder):
        # Setup mock message
        sender = MagicMock()
        sender.id = 123
        sender.username = "user"
        
        chat = MagicMock()
        chat.username = "chat"
        
        msg = create_mock_message(sender=sender, chat=chat)
        
        # Test record_forward
        record_id = await temp_recorder.record_forward(
            message_obj=msg,
            source_chat_id=1001,
            target_chat_id=2002,
            rule_id=10,
            forward_type="auto"
        )
        
        assert record_id != ""
        
        # Verify files created
        # 1. Daily file
        daily_file = temp_recorder.dirs['daily'] / f"{datetime.now().strftime('%Y-%m-%d')}.jsonl"
        assert daily_file.exists()
        with open(daily_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            assert len(lines) == 1
            data = json.loads(lines[0])
            assert data['record_id'] == record_id
            assert data['chat_info']['source_chat_id'] == 1001
        
        # 2. Rule file
        rule_file = temp_recorder.dirs['rules'] / "rule_10.jsonl"
        assert rule_file.exists()
        
        # 3. Chat file
        chat_file = temp_recorder.dirs['chats'] / "chat_2002.jsonl"
        assert chat_file.exists()
        
        # 4. User file
        user_file = temp_recorder.dirs['users'] / "user_123.jsonl"
        assert user_file.exists()
        
        # 5. Stats file
        stats_file = temp_recorder.dirs['summary'] / f"{datetime.now().strftime('%Y-%m')}_stats.json"
        assert stats_file.exists()
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
            today = datetime.now().strftime('%Y-%m-%d')
            assert stats[today]['total_forwards'] == 1
            assert stats[today]['users']['123'] == 1

    async def test_duplicate_stats_update(self, temp_recorder):
        # Record twice
        msg = create_mock_message()
        await temp_recorder.record_forward(msg, 1, 2)
        await temp_recorder.record_forward(msg, 1, 2)
        
        stats_file = temp_recorder.dirs['summary'] / f"{datetime.now().strftime('%Y-%m')}_stats.json"
        with open(stats_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)
            today = datetime.now().strftime('%Y-%m-%d')
            assert stats[today]['total_forwards'] == 2

    async def test_get_daily_summary(self, temp_recorder):
        # Pre-populate stats
        today = datetime.now().strftime('%Y-%m-%d')
        month = datetime.now().strftime('%Y-%m')
        stats_data = {
            today: {
                'total_forwards': 100,
                'users': {'1': 10}
            }
        }
        stats_file = temp_recorder.dirs['summary'] / f"{month}_stats.json"
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(stats_data, f)
            
        summary = await temp_recorder.get_daily_summary(today)
        assert summary['total_forwards'] == 100

    async def test_get_hourly_distribution(self, temp_recorder):
        # Create a dummy jsonl with timestamps from different hours
        today = datetime.now().strftime('%Y-%m-%d')
        daily_file = temp_recorder.dirs['daily'] / f"{today}.jsonl"
        
        # Hour 08 and Hour 10
        records = [
            {'timestamp': f"{today}T08:00:00"},
            {'timestamp': f"{today}T08:30:00"},
            {'timestamp': f"{today}T10:15:00"},
        ]
        
        with open(daily_file, 'w', encoding='utf-8') as f:
            for r in records:
                f.write(json.dumps(r) + '\n')
                
        dist = await temp_recorder.get_hourly_distribution(today)
        assert dist['08'] == 2
        assert dist['10'] == 1
        assert dist['09'] == 0

    async def test_search_records(self, temp_recorder):
        # Setup specific file for search
        # Search by chat_id
        chat_id = 999
        chat_file = temp_recorder.dirs['chats'] / f"chat_{chat_id}.jsonl"
        
        records = [
            {'record_id': '1', 'timestamp': '2023-01-01T10:00:00', 'data': 'rec1'},
            {'record_id': '2', 'timestamp': '2023-01-01T11:00:00', 'data': 'rec2'}
        ]
        
        with open(chat_file, 'w', encoding='utf-8') as f:
            for r in records:
                f.write(json.dumps(r) + '\n')
                
        # Test search
        result = await temp_recorder.search_records(chat_id=chat_id)
        assert len(result) == 2
        
        # Test default date search (empty if no daily file)
        result_date = await temp_recorder.search_records(start_date='2023-01-01')
        assert len(result_date) == 0 # Because we didn't write to daily file 2023-01-01

    async def test_extract_message_info_photo(self, temp_recorder):
        # Mock a photo message
        photo_size = MagicMock()
        photo_size.size = 1024
        
        photo = MagicMock()
        photo.sizes = [photo_size]
        photo.w = 500
        photo.h = 500
        
        media = MagicMock()
        media.photo = photo
        del media.document # Ensure it doesn't have document
        
        msg = create_mock_message(media=media)
        
        info = await temp_recorder._extract_message_info(msg)
        assert info['type'] == 'photo'
        assert info['size_bytes'] == 1024
        assert info['file_info']['width'] == 500
