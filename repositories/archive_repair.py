#!/usr/bin/env python3
"""
归档系统修复工具
用于修复归档过程中的常见问题
"""
import shutil
from datetime import datetime

import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)


def repair_bloom_index() -> bool:
    """修复Bloom索引系统"""
    try:
        logger.debug("开始修复Bloom索引系统")
        from repositories.bloom_index import BLOOM_ROOT, bloom

        logger.info("开始修复Bloom索引系统...")

        # 1. 确保目录存在
        logger.debug(f"确保Bloom根目录存在: {BLOOM_ROOT}")
        Path(BLOOM_ROOT).mkdir(parents=True, exist_ok=True)
        media_signatures_dir = os.path.join(BLOOM_ROOT, "media_signatures")
        logger.debug(f"确保media_signatures目录存在: {media_signatures_dir}")
        Path(media_signatures_dir).mkdir(parents=True, exist_ok=True)

        # 2. 检查是否需要重建索引
        logger.debug("检查Bloom索引文件")
        bloom_files = list(Path(BLOOM_ROOT).rglob("*.bf"))
        logger.debug(f"找到 {len(bloom_files)} 个Bloom索引文件")
        if not bloom_files:
            logger.info("未发现Bloom索引文件，尝试从归档重建...")
            count = bloom.rebuild_media_signatures()
            logger.info(f"从归档重建Bloom索引完成，处理了约 {count} 条记录")
        else:
            logger.info(f"发现 {len(bloom_files)} 个Bloom索引文件")

        # 3. 测试Bloom索引功能
        logger.debug("测试Bloom索引功能")
        test_data = [
            {
                "chat_id": "999999",
                "signature": "repair_test_sig",
                "content_hash": "repair_test_hash",
            }
        ]
        logger.debug("添加测试数据")
        bloom.add_batch("media_signatures", test_data, ["signature", "content_hash"])

        # 验证添加是否成功
        logger.debug("验证测试数据")
        contains_sig = bloom.probably_contains(
            "media_signatures", "999999", "repair_test_sig"
        )
        contains_hash = bloom.probably_contains(
            "media_signatures", "999999", "repair_test_hash"
        )
        logger.debug(f"测试结果: signature={contains_sig}, hash={contains_hash}")
        if contains_sig and contains_hash:
            logger.info("✅ Bloom索引功能测试通过")
            # 清理测试生成的 .bf 文件
            try:
                from repositories.bloom_index import BLOOM_ROOT
                test_bf = os.path.join(BLOOM_ROOT, "media_signatures", "999999.bf")
                if os.path.exists(test_bf):
                    os.remove(test_bf)
                    logger.debug(f"已清理测试 Bloom 文件: {test_bf}")
            except Exception as e:
                logger.warning(f"清理测试 Bloom 文件失败: {e}")
            return True
        else:
            logger.error("❌ Bloom索引功能测试失败")
            return False

    except Exception as e:
        logger.error(f"修复Bloom索引失败: {e}")
        logger.debug("修复Bloom索引失败详细信息", exc_info=True)
        return False


def repair_archive_directories() -> bool:
    """修复归档目录结构"""
    try:
        logger.debug("开始修复归档目录结构")
        from repositories.archive_store import ARCHIVE_ROOT

        logger.info("开始修复归档目录结构...")

        # 要创建的目录列表
        directories = [
            ARCHIVE_ROOT,
            os.path.join(ARCHIVE_ROOT, "media_signatures"),
            os.path.join(ARCHIVE_ROOT, "error_logs"),
            os.path.join(ARCHIVE_ROOT, "rule_logs"),
            os.path.join(ARCHIVE_ROOT, "task_queue"),
            os.path.join(ARCHIVE_ROOT, "chat_statistics"),
            os.path.join(ARCHIVE_ROOT, "rule_statistics"),
        ]

        for directory in directories:
            try:
                logger.debug(f"处理目录: {directory}")
                Path(directory).mkdir(parents=True, exist_ok=True)

                # 检查目录是否可写
                test_file = os.path.join(directory, ".write_test")
                logger.debug(f"测试目录可写性: {directory}")
                with open(test_file, "w") as f:
                    f.write("test")
                os.remove(test_file)

                logger.info(f"✅ 目录 {directory} 正常")
            except Exception as e:
                logger.error(f"❌ 目录 {directory} 有问题: {e}")
                logger.debug("目录检查失败详细信息", exc_info=True)
                return False

        return True

    except Exception as e:
        logger.error(f"修复归档目录失败: {e}")
        logger.debug("修复归档目录失败详细信息", exc_info=True)
        return False


def check_dependencies() -> bool:
    """检查依赖项是否可用"""
    logger.debug("检查依赖项")
    dependencies = []

    # 检查DuckDB
    try:
        logger.debug("检查 DuckDB")
        import duckdb

        con = duckdb.connect(":memory:")
        try:
            con.execute("SELECT 1")
        finally:
            con.close()
        dependencies.append(("DuckDB", True, ""))
    except Exception as e:
        dependencies.append(("DuckDB", False, str(e)))

    # 检查pandas（可选）
    try:
        logger.debug("检查 Pandas")

        dependencies.append(("Pandas", True, ""))
    except Exception as e:
        dependencies.append(("Pandas", False, f"可选依赖: {e}"))

    all_ok = True
    for name, ok, error in dependencies:
        status = "✅" if ok else "❌"
        logger.info(f"{status} {name}: {'可用' if ok else error}")
        if not ok and name in ["DuckDB"]:  # 必需依赖
            all_ok = False

    return all_ok


def force_rebuild_system() -> bool:
    """强制重建整个归档系统"""
    try:
        logger.debug("开始强制重建归档系统")
        logger.info("开始强制重建归档系统...")

        # 1. 检查依赖
        logger.debug("检查依赖")
        if not check_dependencies():
            logger.error("依赖检查失败，无法继续")
            return False

        # 2. 重建目录
        logger.debug("重建目录")
        if not repair_archive_directories():
            logger.error("目录重建失败")
            return False

        # 3. 重建Bloom索引
        logger.debug("重建Bloom索引")
        if not repair_bloom_index():
            logger.error("Bloom索引重建失败")
            return False

        # 4. 测试归档写入
        try:
            logger.debug("测试归档写入")
            from repositories.archive_store import write_parquet

            test_data = [
                {
                    "test_field": "rebuild_test",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ]
            result = write_parquet("system_test", test_data)
            if result:
                logger.info("✅ 归档写入测试通过")
                # 清理测试数据
                try:
                    from core.config import settings
                    test_path = os.path.join(
                        str(settings.ARCHIVE_ROOT), "system_test"
                    )
                    if os.path.exists(test_path):
                        logger.debug(f"清理测试数据: {test_path}")
                        shutil.rmtree(test_path)
                except Exception as e:
                    logger.warning(f"清理测试数据失败: {e}")
                    logger.debug("清理测试数据失败详细信息", exc_info=True)
            else:
                logger.error("❌ 归档写入测试失败")
                return False
        except Exception as e:
            logger.error(f"归档写入测试异常: {e}")
            logger.debug("归档写入测试异常详细信息", exc_info=True)
            return False

        logger.info("✅ 归档系统重建完成")
        return True

    except Exception as e:
        logger.error(f"强制重建系统失败: {e}")
        logger.debug("强制重建系统失败详细信息", exc_info=True)
        return False


def clean_corrupted_files() -> int:
    """清理损坏的归档文件"""
    logger.debug("开始清理损坏的归档文件")
    cleaned = 0
    try:
        from repositories.archive_store import ARCHIVE_ROOT
        from repositories.bloom_index import BLOOM_ROOT

        # 清理可能损坏的parquet文件
        for root_dir in [ARCHIVE_ROOT, BLOOM_ROOT]:
            if os.path.exists(root_dir):
                logger.debug(f"扫描目录: {root_dir}")
                for root, dirs, files in os.walk(root_dir):
                    for file in files:
                        file_path = os.path.join(root, file)
                        try:
                            # 检查文件大小（空文件可能有问题）
                            size = os.path.getsize(file_path)
                            logger.debug(f"检查文件: {file_path}, 大小: {size}")
                            if size == 0:
                                logger.warning(f"发现空文件，删除: {file_path}")
                                os.remove(file_path)
                                cleaned += 1
                            # 检查临时文件
                            elif file.endswith(".tmp"):
                                logger.info(f"清理临时文件: {file_path}")
                                os.remove(file_path)
                                cleaned += 1
                        except Exception as e:
                            logger.warning(f"清理文件失败 {file_path}: {e}")
                            logger.debug("清理文件失败详细信息", exc_info=True)

        logger.info(f"清理了 {cleaned} 个问题文件")
        return cleaned

    except Exception as e:
        logger.error(f"清理损坏文件失败: {e}")
        logger.debug("清理损坏文件失败详细信息", exc_info=True)
        return 0


if __name__ == "__main__":
    import argparse

    import sys

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
    )

    parser = argparse.ArgumentParser(description="归档系统修复工具")
    parser.add_argument("--repair-bloom", action="store_true", help="修复Bloom索引")
    parser.add_argument("--repair-dirs", action="store_true", help="修复目录结构")
    parser.add_argument("--check-deps", action="store_true", help="检查依赖")
    parser.add_argument("--force-rebuild", action="store_true", help="强制重建整个系统")
    parser.add_argument("--clean-corrupted", action="store_true", help="清理损坏文件")
    parser.add_argument("--all", action="store_true", help="执行全部修复操作")

    args = parser.parse_args()

    if not any(vars(args).values()):
        parser.print_help()
        sys.exit(1)

    success = True

    if args.all or args.check_deps:
        print("🔍 检查依赖...")
        if not check_dependencies():
            success = False

    if args.all or args.clean_corrupted:
        print("🧹 清理损坏文件...")
        clean_corrupted_files()

    if args.all or args.repair_dirs:
        print("📁 修复目录结构...")
        if not repair_archive_directories():
            success = False

    if args.all or args.repair_bloom:
        print("🌸 修复Bloom索引...")
        if not repair_bloom_index():
            success = False

    if args.force_rebuild:
        print("🚧 强制重建系统...")
        if not force_rebuild_system():
            success = False

    if success:
        print("✅ 修复完成！")
        sys.exit(0)
    else:
        print("❌ 修复过程中出现错误")
        sys.exit(1)
