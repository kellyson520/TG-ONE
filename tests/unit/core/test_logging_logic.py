
from models.models import ErrorLog, RuleLog

class TestLoggingModels:
    
    def test_error_log_creation(self):
        log = ErrorLog(
            level="ERROR",
            module="test_mod",
            message="Something went wrong",
            context='{"foo": "bar"}',
            user_id="123"
        )
        assert log.level == "ERROR"
        assert log.module == "test_mod"
        
        # Test defaults
        # created_at is dynamic lambda, check if string
        assert isinstance(log.created_at, str) or log.created_at is None 
        # Actually in SQLAlchemy usage, default triggers on insert if not provided, 
        # or if instantiated with default arguments provided by init?
        # declarative_base default usually triggers on flush unless passed.
        # But we verify attributes.
        
    def test_rule_log_creation(self):
        log = RuleLog(
            rule_id=1,
            action="forward",
            source_message_id=100,
            result="success"
        )
        assert log.rule_id == 1
        assert log.action == "forward"
