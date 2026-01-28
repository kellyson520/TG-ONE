#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite -> PostgreSQL/TiDB 迁移脚本（一次性导入）

用法（需先在 .env 或环境变量中配置 DATABASE_URL_SQLITE 与 DATABASE_URL_TARGET）：
  python scripts/sqlite_to_postgres.py

环境变量：
  DATABASE_URL_SQLITE=sqlite:///./db/forward.db
  DATABASE_URL_TARGET=postgresql+psycopg2://user:pass@host:5432/dbname
    # TiDB 也可使用 mysql+pymysql://... 或 TiDB 驱动串

说明：
  - 通过 SQLAlchemy 反射源库结构，在目标库创建缺失的表（不做复杂类型变换）
  - 逐表分页 copy，支持批量大小可配（MIGRATE_BATCH_SIZE）
  - 简化处理：不迁移自增序列当前值、触发器、视图等；如需请在迁移后手工校验
"""

import os
import sys
import math
import logging
from sqlalchemy import create_engine, MetaData, Table, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(level=logging.INFO, format='[%(asctime)s] %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

BATCH_SIZE = int(os.getenv('MIGRATE_BATCH_SIZE', '5000'))


def _create_engine(url: str) -> Engine:
	return create_engine(url, pool_pre_ping=True)


def _reflect_metadata(engine: Engine) -> MetaData:
	meta = MetaData()
	meta.reflect(bind=engine)
	return meta


def _ensure_tables(target_engine: Engine, source_meta: MetaData) -> None:
	"""在目标库创建源库中缺失的表（字段类型按方言推断）。"""
	logger.info('检查并创建目标库缺失的表...')
	source_meta.bind = target_engine
	for tbl in source_meta.sorted_tables:
		try:
			# checkfirst=True: 仅当不存在时创建
			logger.info(f'确保表存在: {tbl.name}')
			tbl.create(bind=target_engine, checkfirst=True)
		except Exception as e:
			logger.warning(f'创建表失败 {tbl.name}: {e}')


def _count_rows(engine: Engine, table: Table) -> int:
	with engine.connect() as conn:
		res = conn.execute(text(f'SELECT COUNT(*) FROM {table.name}'))
		return int(res.scalar() or 0)


def _copy_table(source_engine: Engine, target_engine: Engine, table: Table) -> int:
	"""分页拷贝表数据到目标库。返回导入行数。"""
	row_count = _count_rows(source_engine, table)
	if row_count == 0:
		logger.info(f'{table.name}: 无数据，跳过')
		return 0
	pages = int(math.ceil(row_count / float(BATCH_SIZE)))
	logger.info(f'{table.name}: 共 {row_count} 行，批次 {pages} (batch={BATCH_SIZE})')

	SourceSession = sessionmaker(bind=source_engine)
	TargetSession = sessionmaker(bind=target_engine)
	source_sess = SourceSession()
	target_sess = TargetSession()

	inserted = 0
	cols = [c for c in table.columns]
	try:
		for i in range(pages):
			offset = i * BATCH_SIZE
			rows = source_sess.execute(select(table).limit(BATCH_SIZE).offset(offset)).fetchall()
			if not rows:
				break
			payload = [dict(zip([c.name for c in cols], r)) for r in rows]
			if payload:
				try:
					target_sess.execute(table.insert(), payload)
				except Exception as ie:
					logger.warning(f'{table.name} 批量插入失败，改为逐行: {ie}')
					for row in payload:
						try:
							target_sess.execute(table.insert().values(**row))
						except Exception as se:
							logger.error(f'{table.name} 插入失败（跳过）: {se}')
							continue
				inserted += len(payload)
				target_sess.commit()
			logger.info(f'{table.name}: 进度 {min(inserted, row_count)}/{row_count}')
	finally:
		try:
			source_sess.close()
			target_sess.close()
		except Exception:
			pass
	return inserted


def main():
	src_url = os.getenv('DATABASE_URL_SQLITE', 'sqlite:///./db/forward.db')
	tgt_url = os.getenv('DATABASE_URL_TARGET')
	if not tgt_url:
		logger.error('请设置 DATABASE_URL_TARGET 目标库连接串')
		sys.exit(1)

	logger.info(f'源库: {src_url}')
	logger.info(f'目标库: {tgt_url}')

	source_engine = _create_engine(src_url)
	target_engine = _create_engine(tgt_url)
	# 反射源库结构
	source_meta = _reflect_metadata(source_engine)
	# 确保目标库表存在
	_ensure_tables(target_engine, source_meta)

	# 逐表迁移（按反射顺序）
	total = 0
	for tbl in source_meta.sorted_tables:
		try:
			moved = _copy_table(source_engine, target_engine, tbl)
			total += moved
		except Exception as e:
			logger.error(f'迁移表 {tbl.name} 失败: {e}')
			continue
	logger.info(f'迁移完成，总行数: {total}')


if __name__ == '__main__':
	main()
