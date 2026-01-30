
from models.models import ErrorLog, RuleLog

class TestLoggingModels:
    
    def test_error_log_creation(self):
        log = ErrorLog(
            level="ERROR",
            module="test_mod",
            message="Something went wrong"
        )
        assert log.level == "ERROR"
        assert log.module == "test_mod"
        
    def test_rule_log_creation(self):
        log = RuleLog(
            rule_id=1,
            action="forwarded",
            message_id=100,
            details="success"
        )
        assert log.rule_id == 1
        assert log.action == "forwarded"
        assert log.message_id == 100
