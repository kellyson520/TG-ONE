#!/usr/bin/env python3
"""
数据库日期时间字段修复脚本
检查并修复数据库中可能存在的日期时间格式问题
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from models.models import ForwardRule, Chat, MediaSignature, ForwardLog, SearchResult
from repositories_field_utils import fix_datetime_fields, validate_datetime_fields
from repositories.db_context import db_session

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def fix_model_datetime_fields(model_class, model_name):
    """修复特定模型的日期时间字段"""
    fixed_count = 0
    error_count = 0
    
    try:
        with db_session() as session:
            # 分批处理以避免内存问题
            batch_size = 1000
            offset = 0
            
            while True:
                logger.info(f"处理 {model_name} 批次 {offset // batch_size + 1}...")
                
                objects = session.query(model_class).offset(offset).limit(batch_size).all()
                if not objects:
                    break
                
                batch_fixed = 0
                for obj in objects:
                    try:
                        # 验证日期时间字段
                        invalid_fields = validate_datetime_fields(obj)
                        if invalid_fields:
                            logger.warning(f"{model_name} ID {obj.id} 有无效日期字段: {invalid_fields}")
                        
                        # 修复字段
                        fields_fixed = fix_datetime_fields(obj)
                        if fields_fixed > 0:
                            batch_fixed += fields_fixed
                            logger.info(f"修复 {model_name} ID {obj.id} 的 {fields_fixed} 个字段")
                    
                    except Exception as e:
                        error_count += 1
                        logger.error(f"处理 {model_name} ID {getattr(obj, 'id', '未知')} 时出错: {e}")
                
                if batch_fixed > 0:
                    try:
                        session.commit()
                        fixed_count += batch_fixed
                        logger.info(f"提交 {model_name} 批次修复: {batch_fixed} 个字段")
                    except Exception as e:
                        session.rollback()
                        logger.error(f"提交 {model_name} 批次时出错: {e}")
                        error_count += 1
                
                offset += batch_size
                
                # 如果批次大小小于限制，说明已经处理完所有记录
                if len(objects) < batch_size:
                    break
    
    except Exception as e:
        logger.error(f"处理 {model_name} 时出错: {e}")
        error_count += 1
    
    return fixed_count, error_count

def main():
    """主函数"""
    print("=" * 60)
    print("数据库日期时间字段修复工具")
    print("=" * 60)
    
    # 需要检查的模型列表
    models_to_check = [
        (ForwardRule, "转发规则"),
        (Chat, "聊天记录"),
        (MediaSignature, "媒体签名"),
        (ForwardLog, "转发日志"),
        (SearchResult, "搜索结果")
    ]
    
    total_fixed = 0
    total_errors = 0
    
    for model_class, model_name in models_to_check:
        print(f"\n🔍 检查 {model_name}...")
        try:
            fixed_count, error_count = fix_model_datetime_fields(model_class, model_name)
            total_fixed += fixed_count
            total_errors += error_count
            
            if fixed_count > 0:
                print(f"✅ {model_name}: 修复了 {fixed_count} 个字段")
            else:
                print(f"✅ {model_name}: 无需修复")
                
            if error_count > 0:
                print(f"⚠️ {model_name}: 遇到 {error_count} 个错误")
                
        except Exception as e:
            logger.error(f"检查 {model_name} 时出错: {e}")
            total_errors += 1
    
    print(f"\n" + "=" * 60)
    print("修复完成！")
    print(f"总计修复字段: {total_fixed}")
    print(f"总计错误数: {total_errors}")
    
    if total_fixed > 0:
        print("✅ 数据库日期时间字段已修复")
    else:
        print("✅ 数据库日期时间字段正常，无需修复")
    
    if total_errors > 0:
        print(f"⚠️ 修复过程中遇到 {total_errors} 个错误，请检查日志")
    
    print("=" * 60)

if __name__ == "__main__":
    main()
