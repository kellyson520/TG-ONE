#!/usr/bin/env python3
"""
归档系统初始化工具
确保归档目录结构正确创建，并验证系统可用性
"""
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

from core.config import settings

# 归档系统的配置映射
ARCHIVE_ROOT = str(settings.ARCHIVE_ROOT)
BLOOM_ROOT = str(settings.BLOOM_ROOT)


def init_archive_system() -> bool:
    """初始化归档系统

    Returns:
        bool: 是否成功初始化
    """
    logger.debug("开始初始化归档系统")
    success = True

    # 1. 创建基础目录结构
    directories = [
        ARCHIVE_ROOT,
        BLOOM_ROOT,
        os.path.join(ARCHIVE_ROOT, "media_signatures"),
        os.path.join(ARCHIVE_ROOT, "error_logs"),
        os.path.join(ARCHIVE_ROOT, "rule_logs"),
        os.path.join(ARCHIVE_ROOT, "task_queue"),
        os.path.join(ARCHIVE_ROOT, "chat_statistics"),
        os.path.join(ARCHIVE_ROOT, "rule_statistics"),
        os.path.join(BLOOM_ROOT, "media_signatures"),
    ]

    for directory in directories:
        try:
            logger.debug(f"创建目录: {directory}")
            Path(directory).mkdir(parents=True, exist_ok=True)
            logger.info(f"✅ 创建目录: {directory}")
        except Exception as e:
            logger.error(f"❌ 创建目录失败 {directory}: {e}")
            logger.debug("创建目录失败详细信息", exc_info=True)
            success = False

    # 2. 验证DuckDB可用性 (reuses shared connection from archive_store)
    try:
        logger.debug("验证 DuckDB 可用性")
        from repositories.archive_store import get_connection

        con = get_connection()
        con.execute("SELECT 1 as test")
        result = con.fetchone()
        logger.debug(f"DuckDB test result: {result} (type: {type(result)})")
        # 确保结果正确解包并转换为整数对比
        if result and int(result[0]) == 1:
            logger.info("✅ DuckDB可用性验证通过")
        else:
            logger.error(f"❌ DuckDB测试查询返回异常结果: {result}")
            success = False
    except Exception as e:
        logger.error(f"❌ DuckDB不可用: {e}")
        logger.debug("DuckDB不可用详细信息", exc_info=True)
        success = False

    # 3. 验证Bloom索引系统
    try:
        logger.debug("验证 Bloom 索引系统")
        from repositories.bloom_index import BloomIndex

        bloom = BloomIndex()
        # 测试添加和查询
        test_data = [
            {"chat_id": "123", "signature": "test_sig", "content_hash": "test_hash"}
        ]
        logger.debug("添加测试数据到 Bloom 索引")
        bloom.add_batch("media_signatures", test_data, ["signature", "content_hash"])
        logger.debug("查询 Bloom 索引")
        contains_sig = bloom.probably_contains("media_signatures", "123", "test_sig")
        contains_hash = bloom.probably_contains("media_signatures", "123", "test_hash")
        if contains_sig and contains_hash:
            logger.info("✅ Bloom索引系统验证通过")
            # 清理测试生成的 .bf 文件
            try:
                test_bf = os.path.join(BLOOM_ROOT, "media_signatures", "123.bf")
                if os.path.exists(test_bf):
                    os.remove(test_bf)
                    logger.debug(f"已清理测试 Bloom 文件: {test_bf}")
            except Exception as e:
                logger.warning(f"清理测试 Bloom 文件失败: {e}")
        else:
            logger.error("❌ Bloom索引系统测试失败")
            logger.debug(
                f"测试结果: contains_sig={contains_sig}, contains_hash={contains_hash}"
            )
            success = False
    except Exception as e:
        logger.error(f"❌ Bloom索引系统验证失败: {e}")
        logger.debug("Bloom索引系统验证失败详细信息", exc_info=True)
        success = False

    # 4. 验证Parquet写入
    try:
        logger.debug("验证 Parquet 写入")
        from datetime import datetime

        from repositories.archive_store import write_parquet

        test_data = [
            {"test_field": "test_value", "timestamp": datetime.utcnow().isoformat()}
        ]
        logger.debug("写入测试数据到 Parquet")
        result_dir = write_parquet("test_table", test_data)
        if result_dir:
            logger.info("✅ Parquet写入验证通过")
            # 清理测试文件
            try:
                import shutil

                test_path = os.path.join(ARCHIVE_ROOT, "test_table")
                if os.path.exists(test_path):
                    logger.debug(f"清理测试文件: {test_path}")
                    shutil.rmtree(test_path)
                    logger.debug("清理测试文件完成")
            except Exception as clean_e:
                logger.warning(f"清理测试文件失败: {clean_e}")
                logger.debug("清理测试文件失败详细信息", exc_info=True)
        else:
            logger.error("❌ Parquet写入验证失败")
            success = False
    except Exception as e:
        logger.error(f"❌ Parquet写入验证失败: {e}")
        logger.debug("Parquet写入验证失败详细信息", exc_info=True)
        success = False

    if success:
        logger.debug("归档系统初始化成功")
    else:
        logger.debug("归档系统初始化失败")
    return success


def check_archive_health() -> dict:
    """检查归档系统健康状态

    Returns:
        dict: 健康状态信息
    """
    logger.debug("检查归档系统健康状态")
    health = {"status": "healthy", "checks": {}, "errors": []}

    # 检查目录存在性
    directories = [ARCHIVE_ROOT, BLOOM_ROOT]
    for directory in directories:
        try:
            exists = os.path.exists(directory)
            logger.debug(f"目录 {directory} 存在: {exists}")
            health["checks"][f"directory_{os.path.basename(directory)}"] = exists
            if not exists:
                error_msg = f"目录不存在: {directory}"
                health["errors"].append(error_msg)
                logger.error(error_msg)
        except Exception as e:
            error_msg = f"检查目录失败 {directory}: {e}"
            health["checks"][f"directory_{os.path.basename(directory)}"] = False
            health["errors"].append(error_msg)
            logger.error(error_msg)
            logger.debug("检查目录失败详细信息", exc_info=True)

    # 检查磁盘空间（可选）
    try:
        import shutil

        check_path = ARCHIVE_ROOT if os.path.exists(ARCHIVE_ROOT) else "."
        logger.debug(f"检查磁盘空间: {check_path}")
        total, used, free = shutil.disk_usage(check_path)
        free_gb = free // (1024**3)
        health["checks"]["disk_space_gb"] = free_gb
        logger.debug(
            f"磁盘空间: 总计={total//1024**3}GB, 已用={used//1024**3}GB, 可用={free_gb}GB"
        )
        if free_gb < 1:  # 少于1GB时警告
            error_msg = f"磁盘空间不足: 剩余 {free_gb} GB"
            health["errors"].append(error_msg)
            logger.warning(error_msg)
    except Exception as e:
        error_msg = f"检查磁盘空间失败: {e}"
        health["errors"].append(error_msg)
        logger.error(error_msg)
        logger.debug("检查磁盘空间失败详细信息", exc_info=True)

    # 检查权限
    for directory in [ARCHIVE_ROOT, BLOOM_ROOT]:
        if os.path.exists(directory):
            try:
                # 尝试创建测试文件
                test_file = os.path.join(directory, ".write_test")
                logger.debug(f"测试目录可写性: {directory}")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)
                health["checks"][f"writable_{os.path.basename(directory)}"] = True
                logger.debug(f"目录可写: {directory}")
            except Exception as e:
                health["checks"][f"writable_{os.path.basename(directory)}"] = False
                error_msg = f"目录不可写 {directory}: {e}"
                health["errors"].append(error_msg)
                logger.error(error_msg)
                logger.debug("目录可写性检查失败详细信息", exc_info=True)

    if health["errors"]:
        health["status"] = "unhealthy"
        logger.debug("归档系统健康状态: 不健康")
    else:
        logger.debug("归档系统健康状态: 健康")

    return health


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    print("🚀 开始初始化归档系统...")
    success = init_archive_system()

    if success:
        print("✅ 归档系统初始化成功！")
        print("\n📊 健康状态检查:")
        health = check_archive_health()
        print(f"状态: {health['status']}")
        for check, result in health["checks"].items():
            status = "✅" if result else "❌"
            print(f"  {status} {check}: {result}")
        if health["errors"]:
            print("\n⚠️ 发现问题:")
            for error in health["errors"]:
                print(f"  - {error}")
        sys.exit(0)
    else:
        print("❌ 归档系统初始化失败！")
        sys.exit(1)
