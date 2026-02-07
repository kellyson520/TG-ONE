# Task: Integration Test Mixed Media Flow
## Plan
1.  Initialize Task Environment
    - Create `tests/integration/test_mixed_media_integration.py`
    - Import test fixtures from `conftest.py` and `test_full_pipeline.py`
2.  Implement Test Logic
    - Create `MixedMediaFactory` to generate 8 types of media:
      - Video
      - Text
      - Image
      - Link
      - Sticker
      - Voice
      - File
      - Audio
    - Generate 10 mock messages for each type (Total 80).
    - Add specific filter triggers (e.g., keywords) to some messages to test filtering.
    - Shuffle the list randomly.
3.  Simulate Pipeline
    - Construct `Pipeline` with `RuleLoader`, `Filter`, `Dedup`, `Sender`.
    - Feed messages one by one.
    - Verify:
        - Messages with trigger words ARE filtered.
        - Messages without trigger words are NOT filtered.
        - Messages are forwarded correctly (check `mock_client.send_message`/`send_file` calls).
    - Handle boundary cases: empty text, large file size mock (metadata only), malformed links.
4.  Verify
    - Run `pytest tests/integration/test_mixed_media_integration.py`
    - Ensure all tests pass.
