"""
配置初始化器
负责应用启动时从数据库加载动态配置，避免 Settings 类中的循环依赖
"""
import logging
from typing import Any
from pathlib import Path

logger = logging.getLogger(__name__)

async def load_dynamic_config_from_db(settings_obj: Any) -> None:
    """从数据库加载动态配置，覆盖现有配置"""
    try:
        from services.config_service import config_service
        
        # 从数据库加载所有配置项
        db_configs = await config_service.get_all()
        
        # 更新配置项
        for key, value in db_configs.items():
            if hasattr(settings_obj, key):
                # 获取字段类型并尝试转换值
                # settings_obj is expected to be Pydantic model instance
                field_info = settings_obj.model_fields.get(key)
                if not field_info:
                    continue
                    
                field_type = field_info.annotation
                try:
                    # 根据字段类型转换值
                    converted_value: Any = value
                    if field_type == bool:
                        converted_value = str(value).strip().lower() in ('1','true','yes','on')
                    elif field_type == int:
                        converted_value = int(value)
                    elif field_type == float:
                        converted_value = float(value)
                    elif field_type == Path:
                        converted_value = Path(value)
                    
                    # 更新配置值
                    setattr(settings_obj, key, converted_value)
                    logger.debug(f"从数据库加载配置项: {key} = {converted_value}")
                except Exception as e:
                    logger.warning(f"转换配置项 {key} 值失败: {e}")
    except Exception as e:
        logger.warning(f"从数据库加载动态配置失败: {e}")
