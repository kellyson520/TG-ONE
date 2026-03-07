# Index Optimization: idx_hotword_date_word

## 1. Context
The user requested adding a composite index `idx_hotword_date_word` on `hotwords(date, word)`. 
Based on the current architecture, the `hot_period_stats` table in `hotwords.db` is the correct target, where `date_key` represents the date and `word` represents the hotword.

## 2. Technical Goal
Improve query performance for hotword lookups and summaries that filter by date and word.

## 3. Implementation
- **Table**: `hot_period_stats`
- **Columns**: `date_key`, `word`
- **Index Name**: `idx_hotword_date_word`
- **SQL**: `CREATE INDEX IF NOT EXISTS idx_hotword_date_word ON hot_period_stats(date_key, word);`

### Model Changes
Add the index to `models/hotword.py`:
```python
Index('idx_hotword_date_word', 'date_key', 'word')
```

### Migration Strategy
Since `hotwords.db` does not use a formal migration framework, we will add an explicit `CREATE INDEX IF NOT EXISTS` call in `core/db_init.py` within the `init_hotword_db` function to ensure existing databases are updated.
