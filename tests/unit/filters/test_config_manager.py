import pytest
from unittest.mock import MagicMock, patch, ANY
import json
from filters.config_manager import FilterConfigManager
from models.models import ForwardRule
from enums.enums import HandleMode

@pytest.fixture
def mock_registry():
    registry = MagicMock()
    # Include all filters used in tests to ensure they are added when configuration calls for them
    registry.get_default_order.return_value = ["init", "keyword", "replace", "edit", "push", "sender"]
    registry.validate_filter_config.return_value = (True, [])
    registry.optimize_filter_order.side_effect = lambda x: x
    registry.get_filter_info.return_value = {}
    return registry

@pytest.fixture
def mock_factory():
    factory = MagicMock()
    factory.get_cache_stats.return_value = {}
    return factory

@pytest.fixture
def config_manager(mock_registry, mock_factory):
    with patch("filters.config_manager.get_filter_registry", return_value=mock_registry):
        with patch("filters.config_manager.get_filter_chain_factory", return_value=mock_factory):
            manager = FilterConfigManager()
            return manager

def test_get_default_config(config_manager, mock_registry):
    config = config_manager.get_default_config()
    assert config["version"] == "1.0"
    assert config["filters"] == ["init", "keyword", "replace", "edit", "push", "sender"]
    assert config["created_by"] == "system"

def test_generate_config_for_rule(config_manager, mock_registry):
    rule = MagicMock(spec=ForwardRule)
    rule.id = 1
    # Set attributes
    rule.enable_delay = False
    rule.is_replace = True
    rule.is_ai = False
    rule.enable_comment_button = False
    rule.only_rss = False
    rule.handle_mode = HandleMode.EDIT
    rule.enable_push = True
    rule.is_delete_original = False
    
    # Media attributes
    rule.enable_media_type_filter = False
    rule.enable_media_size_filter = False
    rule.enable_extension_filter = False
    
    rule.enable_duration_filter = False
    rule.enable_resolution_filter = False
    rule.enable_file_size_range = False
    
    config = config_manager._generate_config_for_rule(rule)
    
    assert "init" in config["filters"]
    assert "replace" in config["filters"]
    assert "edit" in config["filters"]
    assert "push" in config["filters"]
    assert "delay" not in config["filters"]

def test_validate_rule_config_valid(config_manager, mock_registry):
    rule = MagicMock(spec=ForwardRule)
    rule.enabled_filters = json.dumps({"filters": ["init", "keyword"]})
    
    result = config_manager.validate_rule_config(rule)
    assert result["valid"] is True
    assert result["config"]["filters"] == ["init", "keyword"]

def test_validate_rule_config_invalid_json(config_manager):
    rule = MagicMock(spec=ForwardRule)
    rule.enabled_filters = "{invalid_json"
    
    result = config_manager.validate_rule_config(rule)
    assert result["valid"] is False
    assert "JSON格式错误" in result["errors"][0]

def test_validate_rule_config_missing_filters(config_manager):
    rule = MagicMock(spec=ForwardRule)
    rule.enabled_filters = json.dumps({"version": "1.0"})
    
    result = config_manager.validate_rule_config(rule)
    # The code checks `if not isinstance(filters, list)` where filters = config.get("filters", []), so empty list is valid?
    # Let's check code: `filters = config.get("filters", [])`. Default is [].
    # But checking source: `if not isinstance(filters, list)`.
    # Wait, if key is missing, filters is [], which IS a list.
    # Ah, let's verify if empty filters list is considered valid by registry mock (it returns True).
    assert result["valid"] is True 

def test_validate_rule_config_invalid_type(config_manager):
    rule = MagicMock(spec=ForwardRule)
    rule.enabled_filters = json.dumps({"filters": "not_a_list"})
    
    result = config_manager.validate_rule_config(rule)
    assert result["valid"] is False
    assert "filters字段应为数组" in result["errors"][0]

def test_migrate_filter_configs(config_manager):
    mock_session = MagicMock()
    
    rule1 = MagicMock(spec=ForwardRule)
    rule1.id = 1
    rule1.enabled_filters = None
    # Set attributes for generation
    rule1.enable_delay = False
    rule1.is_replace = False
    rule1.is_ai = False
    rule1.enable_comment_button = False
    rule1.only_rss = False
    rule1.handle_mode = HandleMode.FORWARD
    rule1.enable_push = False
    rule1.is_delete_original = False
    rule1.enable_media_type_filter = False
    rule1.enable_media_size_filter = False
    rule1.enable_extension_filter = False
    rule1.enable_duration_filter = False
    rule1.enable_resolution_filter = False
    rule1.enable_file_size_range = False
    
    mock_session.query.return_value.filter.return_value.all.return_value = [rule1]
    
    stats = config_manager.migrate_filter_configs(mock_session)
    
    assert stats["migrated_rules"] == 1
    assert stats["failed_rules"] == 0
    assert rule1.enabled_filters is not None
    mock_session.commit.assert_called_once()

def test_save_filter_config_success(config_manager):
    mock_session = MagicMock()
    rule = MagicMock(spec=ForwardRule)
    rule.id = 1
    mock_session.query.return_value.filter_by.return_value.first.return_value = rule
    
    new_config = {"filters": ["init"]}
    
    result = config_manager.save_filter_config(1, new_config, mock_session)
    
    assert result is True
    mock_session.commit.assert_called_once()
    # Mock factory needs to clear cache
    config_manager._factory.clear_cache.assert_called_once()

def test_save_filter_config_fail_validation(config_manager, mock_registry):
    mock_session = MagicMock()
    rule = MagicMock(spec=ForwardRule)
    rule.id = 1
    rule.enabled_filters = "{}"
    mock_session.query.return_value.filter_by.return_value.first.return_value = rule
    
    # Mock registry validation failure
    mock_registry.validate_filter_config.return_value = (False, ["error"])
    
    new_config = {"filters": ["invalid"]}
    
    result = config_manager.save_filter_config(1, new_config, mock_session)
    
    assert result is False
    mock_session.commit.assert_not_called()
    assert rule.enabled_filters == "{}" # Reverted

def test_update_global_config(config_manager, mock_registry):
    mock_registry.get_all_filters.return_value = {"init": {}, "process": {}}
    
    result = config_manager.update_global_config(["init"])
    assert result is True
    config_manager._factory.set_global_disabled_filters.assert_called_once_with(["init"])

def test_update_global_config_invalid(config_manager, mock_registry):
    mock_registry.get_all_filters.return_value = {"init": {}}
    
    result = config_manager.update_global_config(["invalid_filter"])
    assert result is False
    config_manager._factory.set_global_disabled_filters.assert_not_called()
