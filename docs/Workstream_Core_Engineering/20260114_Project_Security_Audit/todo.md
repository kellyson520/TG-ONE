# 项目安全与稳定性改进计划

**创建时间**: 2026-01-14  
**负责人**: 开发团队  
**预计完成时间**: 12周  

---

## 🎯 Phase 1: 紧急修复 (Week 1-2) - CRITICAL

### 1.1 密钥安全修复 ⚠️ URGENT

- [ ] **轮换所有泄露的凭证** (Day 1)
  - [ ] 生成新的 Telegram API_ID 和 API_HASH
  - [ ] 重新创建 BOT_TOKEN
  - [ ] 更新 WEB_ADMIN_PASSWORD
  - [ ] 生成新的 SECRET_KEY 和 RSS_SECRET_KEY
  - [ ] 通知所有用户重新登录

- [ ] **清理 Git 历史** (Day 1-2)
  ```bash
  # 从 Git 历史中删除 .env
  git filter-branch --force --index-filter \
    "git rm --cached --ignore-unmatch .env" \
    --prune-empty --tag-name-filter cat -- --all
  
  # 强制推送
  git push origin --force --all
  git push origin --force --tags
  ```

- [x] **实施 .env 保护** (Day 2)
  - [x] 添加 `.env` 到 `.gitignore`
  - [ ] 创建 `.env.example` 模板
  - [ ] 添加 pre-commit hook 防止提交敏感文件
  ```bash
  # .git/hooks/pre-commit
  #!/bin/bash
  if git diff --cached --name-only | grep -q "^\.env$"; then
    echo "错误: 不允许提交 .env 文件"
    exit 1
  fi
  ```

### 1.2 SECRET_KEY 持久化修复 ⚠️ HIGH

- [ ] **修改配置加载逻辑** (Day 3)
  ```python
  # core/config.py
  def _load_or_create_secret_key() -> str:
      """从文件加载或创建持久化密钥"""
      key_file = Path(__file__).parent.parent / '.secret_key'
      
      # 优先从环境变量读取
      env_key = os.getenv('SECRET_KEY')
      if env_key:
          return env_key
      
      # 从文件读取
      if key_file.exists():
          return key_file.read_text().strip()
      
      # 创建新密钥并持久化
      new_key = secrets.token_hex(32)
      key_file.write_text(new_key)
      key_file.chmod(0o600)  # 仅所有者可读写
      logger.warning(f"已生成新的 SECRET_KEY 并保存到 {key_file}")
      return new_key
  
  SECRET_KEY: str = Field(
      default_factory=_load_or_create_secret_key,
      env="SECRET_KEY"
  )
  ```

- [ ] **添加密钥验证脚本** (Day 3)
  ```python
  # scripts/validate_secret_key.py
  import os
  from pathlib import Path
  
  def validate_secret_key():
      env_key = os.getenv('SECRET_KEY')
      key_file = Path('.secret_key')
      
      if not env_key and not key_file.exists():
          print("❌ 错误: SECRET_KEY 未配置")
          print("请在 .env 中设置 SECRET_KEY 或运行 scripts/generate_secret_key.py")
          exit(1)
      
      print("✅ SECRET_KEY 配置正确")
  
  if __name__ == '__main__':
      validate_secret_key()
  ```

### 1.3 数据库连接池优化 ⚠️ HIGH

- [ ] **调整 SQLite 连接池配置** (Day 4)
  ```python
  # .env
  DB_POOL_SIZE=5          # SQLite 推荐值
  DB_MAX_OVERFLOW=10
  DB_POOL_TIMEOUT=30
  DB_POOL_RECYCLE=3600
  
  # 添加连接池监控
  DB_POOL_PRE_PING=true   # 连接前检查
  ```

- [ ] **添加数据库连接监控** (Day 4)
  ```python
  # utils/db/pool_monitor.py
  from sqlalchemy import event
  from sqlalchemy.pool import Pool
  import logging
  
  logger = logging.getLogger(__name__)
  
  @event.listens_for(Pool, "connect")
  def receive_connect(dbapi_conn, connection_record):
      logger.debug("数据库连接已建立")
  
  @event.listens_for(Pool, "checkout")
  def receive_checkout(dbapi_conn, connection_record, connection_proxy):
      logger.debug("从连接池获取连接")
  
  @event.listens_for(Pool, "checkin")
  def receive_checkin(dbapi_conn, connection_record):
      logger.debug("连接归还到连接池")
  ```

### 1.4 登录安全加固 ⚠️ HIGH

- [ ] **实施速率限制** (Day 5)
  ```python
  # web_admin/security/rate_limiter.py
  from slowapi import Limiter
  from slowapi.util import get_remote_address
  from slowapi.errors import RateLimitExceeded
  
  limiter = Limiter(
      key_func=get_remote_address,
      default_limits=["200/day", "50/hour"]
  )
  
  # 登录端点
  @router.post("/login")
  @limiter.limit("5/minute")
  async def login(request: Request, credentials: LoginRequest):
      ...
  ```

- [ ] **实施账户锁定机制** (Day 5)
  ```python
  # services/security_service.py
  class AccountLockService:
      LOCK_DURATION = 1800  # 30分钟
      MAX_ATTEMPTS = 5
      
      async def record_failed_attempt(self, username: str, ip: str):
          """记录失败尝试"""
          key = f"login_attempts:{username}"
          attempts = await redis.incr(key)
          await redis.expire(key, 300)  # 5分钟内
          
          if attempts >= self.MAX_ATTEMPTS:
              await self.lock_account(username)
      
      async def lock_account(self, username: str):
          """锁定账户"""
          lock_key = f"account_locked:{username}"
          await redis.setex(lock_key, self.LOCK_DURATION, "1")
          logger.warning(f"账户已锁定: {username}")
      
      async def is_account_locked(self, username: str) -> bool:
          """检查账户是否被锁定"""
          lock_key = f"account_locked:{username}"
          return await redis.exists(lock_key)
  ```

### 1.5 测试环境修复 ⚠️ HIGH

- [ ] **修复测试收集错误** (Day 6)
  ```bash
  # 检查编码问题
  python -m pytest tests/ --collect-only -v
  
  # 修复文件编码
  find tests/ -name "*.py" -exec python -c "
  import sys
  with open(sys.argv[1], 'rb') as f:
      content = f.read()
  try:
      content.decode('utf-8')
  except UnicodeDecodeError:
      print(f'编码错误: {sys.argv[1]}')
  " {} \;
  ```

- [ ] **添加测试前置检查** (Day 6)
  ```python
  # tests/conftest.py
  import pytest
  import sys
  
  def pytest_configure(config):
      """测试配置检查"""
      # 检查 Python 版本
      if sys.version_info < (3, 11):
          raise RuntimeError("需要 Python 3.11+")
      
      # 检查必要的环境变量
      required_env = ['DATABASE_URL', 'SECRET_KEY']
      missing = [e for e in required_env if not os.getenv(e)]
      if missing:
          raise RuntimeError(f"缺少环境变量: {missing}")
  ```

---

## 🛡️ Phase 2: 安全加固 (Week 3-6) - HIGH

### 2.1 密钥管理服务集成

- [ ] **评估密钥管理方案** (Week 3)
  - [ ] 调研 HashiCorp Vault
  - [ ] 调研 AWS Secrets Manager
  - [ ] 调研 Azure Key Vault
  - [ ] 选择适合的方案

- [ ] **实施密钥管理** (Week 4)
  ```python
  # utils/secrets/vault_client.py
  import hvac
  
  class VaultClient:
      def __init__(self):
          self.client = hvac.Client(
              url=os.getenv('VAULT_ADDR'),
              token=os.getenv('VAULT_TOKEN')
          )
      
      def get_secret(self, path: str) -> dict:
          """从 Vault 获取密钥"""
          response = self.client.secrets.kv.v2.read_secret_version(
              path=path
          )
          return response['data']['data']
      
      def set_secret(self, path: str, data: dict):
          """设置密钥到 Vault"""
          self.client.secrets.kv.v2.create_or_update_secret(
              path=path,
              secret=data
          )
  ```

### 2.2 密码策略加强

- [ ] **实施强密码策略** (Week 3)
  ```python
  # web_admin/security/password_policy.py
  import re
  from typing import Tuple
  
  class PasswordPolicy:
      MIN_LENGTH = 12
      MAX_LENGTH = 128
      REQUIRE_UPPERCASE = True
      REQUIRE_LOWERCASE = True
      REQUIRE_DIGIT = True
      REQUIRE_SPECIAL = True
      
      # 常见弱密码黑名单
      BLACKLIST = [
          'password', '123456', 'admin123', 'qwerty',
          'letmein', 'welcome', 'monkey', '1234567890'
      ]
      
      @classmethod
      def validate(cls, password: str) -> Tuple[bool, str]:
          """验证密码强度"""
          # 长度检查
          if len(password) < cls.MIN_LENGTH:
              return False, f"密码长度至少{cls.MIN_LENGTH}位"
          
          if len(password) > cls.MAX_LENGTH:
              return False, f"密码长度不能超过{cls.MAX_LENGTH}位"
          
          # 字符类型检查
          if cls.REQUIRE_UPPERCASE and not re.search(r'[A-Z]', password):
              return False, "密码必须包含大写字母"
          
          if cls.REQUIRE_LOWERCASE and not re.search(r'[a-z]', password):
              return False, "密码必须包含小写字母"
          
          if cls.REQUIRE_DIGIT and not re.search(r'\d', password):
              return False, "密码必须包含数字"
          
          if cls.REQUIRE_SPECIAL and not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
              return False, "密码必须包含特殊字符"
          
          # 黑名单检查
          if password.lower() in cls.BLACKLIST:
              return False, "密码过于简单，请使用更复杂的密码"
          
          # 重复字符检查
          if re.search(r'(.)\1{2,}', password):
              return False, "密码不能包含3个或以上重复字符"
          
          return True, "密码强度合格"
  ```

- [ ] **添加密码历史记录** (Week 3)
  ```python
  # models/password_history.py
  from sqlalchemy import Column, Integer, String, DateTime
  from datetime import datetime
  
  class PasswordHistory(Base):
      __tablename__ = 'password_history'
      
      id = Column(Integer, primary_key=True)
      user_id = Column(Integer, ForeignKey('users.id'))
      password_hash = Column(String(255))
      created_at = Column(DateTime, default=datetime.utcnow)
      
      @classmethod
      async def check_reuse(cls, user_id: int, new_password: str, count: int = 5):
          """检查密码是否在最近N次中使用过"""
          recent_passwords = await cls.query.filter_by(
              user_id=user_id
          ).order_by(cls.created_at.desc()).limit(count).all()
          
          for old_pw in recent_passwords:
              if verify_password(new_password, old_pw.password_hash):
                  return False, "不能使用最近5次使用过的密码"
          
          return True, "密码可用"
  ```

### 2.3 审计日志系统

- [ ] **实施审计日志** (Week 4)
  ```python
  # models/audit_log.py
  from sqlalchemy import Column, Integer, String, DateTime, JSON
  from datetime import datetime
  
  class AuditLog(Base):
      __tablename__ = 'audit_logs'
      
      id = Column(Integer, primary_key=True)
      user_id = Column(Integer, ForeignKey('users.id'), nullable=True)
      action = Column(String(100))  # login, logout, create_rule, delete_rule
      resource_type = Column(String(50))  # user, rule, config
      resource_id = Column(String(100))
      ip_address = Column(String(45))
      user_agent = Column(String(255))
      details = Column(JSON)
      created_at = Column(DateTime, default=datetime.utcnow)
      
      @classmethod
      async def log(cls, action: str, user_id: int = None, **kwargs):
          """记录审计日志"""
          log_entry = cls(
              user_id=user_id,
              action=action,
              **kwargs
          )
          await log_entry.save()
  ```

- [ ] **添加审计日志查询接口** (Week 4)
  ```python
  # web_admin/routers/audit_router.py
  @router.get("/audit-logs")
  async def get_audit_logs(
      skip: int = 0,
      limit: int = 100,
      action: str = None,
      user_id: int = None,
      start_date: datetime = None,
      end_date: datetime = None
  ):
      """查询审计日志"""
      query = AuditLog.query
      
      if action:
          query = query.filter_by(action=action)
      if user_id:
          query = query.filter_by(user_id=user_id)
      if start_date:
          query = query.filter(AuditLog.created_at >= start_date)
      if end_date:
          query = query.filter(AuditLog.created_at <= end_date)
      
      logs = await query.offset(skip).limit(limit).all()
      return logs
  ```

### 2.4 IP 白名单

- [ ] **实施 IP 访问控制** (Week 5)
  ```python
  # web_admin/security/ip_whitelist.py
  from fastapi import Request, HTTPException
  from ipaddress import ip_address, ip_network
  
  class IPWhitelistMiddleware:
      def __init__(self, app, whitelist: list):
          self.app = app
          self.whitelist = [ip_network(ip) for ip in whitelist]
      
      async def __call__(self, request: Request, call_next):
          client_ip = ip_address(request.client.host)
          
          # 检查是否在白名单中
          if not any(client_ip in network for network in self.whitelist):
              raise HTTPException(
                  status_code=403,
                  detail=f"IP {client_ip} 不在白名单中"
              )
          
          return await call_next(request)
  ```

### 2.5 Docker 安全加固

- [ ] **添加非 root 用户** (Week 5)
  ```dockerfile
  # Dockerfile
  # 创建非 root 用户
  RUN groupadd -r appuser && useradd -r -g appuser appuser
  
  # 设置文件权限
  RUN chown -R appuser:appuser /app
  
  # 切换到非 root 用户
  USER appuser
  
  # 健康检查
  HEALTHCHECK --interval=30s --timeout=10s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:9000/health', timeout=5)"
  ```

- [ ] **优化 docker-compose.yml** (Week 5)
  ```yaml
  # docker-compose.yml
  services:
    telegram-forwarder:
      # 安全配置
      security_opt:
        - no-new-privileges:true
      cap_drop:
        - ALL
      cap_add:
        - NET_BIND_SERVICE
      
      # 资源限制
      deploy:
        resources:
          limits:
            cpus: '2'
            memory: 2G
          reservations:
            memory: 512M
      
      # 精确挂载
      volumes:
        - ./db:/app/db:rw
        - ./logs:/app/logs:rw
        - ./sessions:/app/sessions:rw
        - ./temp:/app/temp:rw
        # 不要挂载整个项目目录
  ```

---

## 🔧 Phase 3: 稳定性提升 (Week 7-10) - MEDIUM

### 3.1 异常处理优化

- [ ] **创建异常处理指南** (Week 7)
  ```python
  # docs/exception_handling_guide.md
  # 异常处理最佳实践
  
  ## 1. 捕获具体异常
  ✅ 推荐:
  try:
      result = risky_operation()
  except FileNotFoundError:
      logger.warning("文件不存在")
  except PermissionError:
      logger.error("权限不足")
  except OSError as e:
      logger.error(f"系统错误: {e}")
      raise
  
  ❌ 避免:
  try:
      result = risky_operation()
  except Exception:
      pass  # 吞掉所有异常
  ```

- [ ] **重构核心模块异常处理** (Week 7-8)
  - [ ] `core/pipeline.py`
  - [ ] `core/container.py`
  - [ ] `services/` 目录
  - [ ] `handlers/` 目录

### 3.2 测试覆盖率提升

- [ ] **设置覆盖率目标** (Week 7)
  ```ini
  # pytest.ini
  [pytest]
  addopts = 
      --cov=core
      --cov=services
      --cov=handlers
      --cov=middlewares
      --cov-report=html
      --cov-report=term-missing
      --cov-fail-under=80
  ```

- [ ] **补充单元测试** (Week 8-9)
  - [ ] 核心业务逻辑测试
  - [ ] 边界条件测试
  - [ ] 异常场景测试

- [ ] **添加集成测试** (Week 9)
  - [ ] 消息转发端到端测试
  - [ ] 去重逻辑测试
  - [ ] Web API 集成测试

### 3.3 性能监控

- [ ] **集成 Prometheus** (Week 8)
  ```python
  # utils/monitoring/prometheus.py
  from prometheus_client import Counter, Histogram, Gauge
  
  # 业务指标
  message_processed = Counter(
      'message_processed_total',
      'Total messages processed',
      ['status', 'rule_id']
  )
  
  message_processing_duration = Histogram(
      'message_processing_duration_seconds',
      'Message processing duration',
      ['rule_id']
  )
  
  active_rules = Gauge(
      'active_rules',
      'Number of active forwarding rules'
  )
  ```

- [ ] **添加性能分析** (Week 8)
  ```python
  # utils/profiling/profiler.py
  import cProfile
  import pstats
  from functools import wraps
  
  def profile(output_file=None):
      """性能分析装饰器"""
      def decorator(func):
          @wraps(func)
          def wrapper(*args, **kwargs):
              profiler = cProfile.Profile()
              profiler.enable()
              
              result = func(*args, **kwargs)
              
              profiler.disable()
              stats = pstats.Stats(profiler)
              stats.sort_stats('cumulative')
              
              if output_file:
                  stats.dump_stats(output_file)
              else:
                  stats.print_stats(20)
              
              return result
          return wrapper
      return decorator
  ```

### 3.4 断路器模式

- [ ] **实施断路器** (Week 9)
  ```python
  # utils/resilience/circuit_breaker.py
  from enum import Enum
  from datetime import datetime, timedelta
  
  class CircuitState(Enum):
      CLOSED = "closed"
      OPEN = "open"
      HALF_OPEN = "half_open"
  
  class CircuitBreaker:
      def __init__(self, failure_threshold=5, timeout=60):
          self.failure_threshold = failure_threshold
          self.timeout = timeout
          self.failure_count = 0
          self.last_failure_time = None
          self.state = CircuitState.CLOSED
      
      async def call(self, func, *args, **kwargs):
          """执行受保护的调用"""
          if self.state == CircuitState.OPEN:
              if datetime.now() - self.last_failure_time > timedelta(seconds=self.timeout):
                  self.state = CircuitState.HALF_OPEN
              else:
                  raise Exception("Circuit breaker is OPEN")
          
          try:
              result = await func(*args, **kwargs)
              self.on_success()
              return result
          except Exception as e:
              self.on_failure()
              raise e
      
      def on_success(self):
          """成功回调"""
          self.failure_count = 0
          self.state = CircuitState.CLOSED
      
      def on_failure(self):
          """失败回调"""
          self.failure_count += 1
          self.last_failure_time = datetime.now()
          
          if self.failure_count >= self.failure_threshold:
              self.state = CircuitState.OPEN
  ```

### 3.5 日志系统优化

- [ ] **简化日志配置** (Week 10)
  ```python
  # .env (简化后)
  LOG_LEVEL=INFO
  LOG_FORMAT=json
  LOG_MAX_SIZE=50MB
  LOG_BACKUP_COUNT=10
  LOG_ASYNC=true
  ```

- [ ] **实施结构化日志** (Week 10)
  ```python
  # utils/logging/structured_logger.py
  import structlog
  
  structlog.configure(
      processors=[
          structlog.stdlib.filter_by_level,
          structlog.stdlib.add_logger_name,
          structlog.stdlib.add_log_level,
          structlog.stdlib.PositionalArgumentsFormatter(),
          structlog.processors.TimeStamper(fmt="iso"),
          structlog.processors.StackInfoRenderer(),
          structlog.processors.format_exc_info,
          structlog.processors.UnicodeDecoder(),
          structlog.processors.JSONRenderer()
      ],
      context_class=dict,
      logger_factory=structlog.stdlib.LoggerFactory(),
      cache_logger_on_first_use=True,
  )
  
  logger = structlog.get_logger()
  logger.info("user_login", user_id=123, ip="1.2.3.4")
  ```

---

## 🚀 Phase 4: 架构优化 (Week 11-12) - LOW

### 4.1 数据库迁移评估

- [ ] **PostgreSQL 迁移方案** (Week 11)
  - [ ] 性能对比测试
  - [ ] 迁移脚本编写
  - [ ] 数据一致性验证

### 4.2 缓存层实施

- [ ] **Redis 集成** (Week 11)
  ```python
  # utils/cache/redis_client.py
  import aioredis
  
  class RedisCache:
      def __init__(self):
          self.redis = None
      
      async def connect(self):
          self.redis = await aioredis.create_redis_pool(
              os.getenv('REDIS_URL', 'redis://localhost')
          )
      
      async def get(self, key: str):
          return await self.redis.get(key)
      
      async def set(self, key: str, value: str, expire: int = 3600):
          await self.redis.setex(key, expire, value)
  ```

### 4.3 CI/CD 流水线

- [ ] **GitHub Actions 配置** (Week 12)
  ```yaml
  # .github/workflows/ci.yml
  name: CI/CD Pipeline
  
  on:
    push:
      branches: [ main, develop ]
    pull_request:
      branches: [ main ]
  
  jobs:
    test:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v2
        
        - name: Set up Python
          uses: actions/setup-python@v2
          with:
            python-version: '3.11'
        
        - name: Install dependencies
          run: |
            pip install -r requirements.txt
            pip install pytest pytest-cov
        
        - name: Run tests
          run: |
            pytest --cov=. --cov-report=xml
        
        - name: Upload coverage
          uses: codecov/codecov-action@v2
    
    security-scan:
      runs-on: ubuntu-latest
      steps:
        - uses: actions/checkout@v2
        
        - name: Run Bandit
          run: |
            pip install bandit
            bandit -r . -f json -o bandit-report.json
        
        - name: Run Safety
          run: |
            pip install safety
            safety check --json
  ```

---

## 📊 进度跟踪

### Week 1-2 检查点
- [ ] 所有密钥已轮换
- [ ] .env 已从 Git 移除
- [ ] SECRET_KEY 持久化完成
- [ ] 数据库连接池优化完成
- [ ] 登录速率限制实施
- [ ] 测试环境修复

### Week 3-6 检查点
- [ ] 密钥管理服务集成
- [ ] 强密码策略实施
- [ ] 审计日志系统上线
- [ ] IP 白名单配置
- [ ] Docker 安全加固

### Week 7-10 检查点
- [ ] 异常处理重构完成
- [ ] 测试覆盖率达到 80%+
- [ ] 性能监控系统上线
- [ ] 断路器模式实施
- [ ] 日志系统优化

### Week 11-12 检查点
- [ ] 数据库迁移方案确定
- [ ] Redis 缓存集成
- [ ] CI/CD 流水线上线

---

## 🎯 成功指标

### 安全性指标
- [ ] 无敏感信息泄露
- [ ] 所有密钥加密存储
- [ ] 登录失败率 < 1%
- [ ] 无安全漏洞（通过 Bandit/Safety 扫描）

### 稳定性指标
- [ ] 系统可用性 > 99.9%
- [ ] 平均故障恢复时间 < 5分钟
- [ ] 测试覆盖率 > 80%
- [ ] 无 P0/P1 级别 Bug

### 性能指标
- [ ] API 响应时间 < 200ms (P95)
- [ ] 消息处理延迟 < 1s
- [ ] 数据库查询时间 < 100ms (P95)
- [ ] 内存使用 < 2GB

---

## 📝 备注

1. **优先级调整**: 根据实际情况可调整任务优先级
2. **资源分配**: 建议至少 2 名开发人员全职投入
3. **风险管理**: 每周进行风险评估和进度审查
4. **文档更新**: 所有变更必须同步更新文档

---

**最后更新**: 2026-01-14  
**下次审查**: 2026-01-21
