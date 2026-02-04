from fastapi import Request
import uuid
import time
import logging
from core.context import trace_id_var
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)

class TraceMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. 提取或生成 Trace ID
        trace_id = request.headers.get("X-Trace-ID")
        if not trace_id:
            trace_id = str(uuid.uuid4())
        
        # 2. 设置上下文变量
        token = trace_id_var.set(trace_id)
        
        start_time = time.time()
        client_ip = request.client.host if request.client else "unknown"
        
        try:
            # 记录请求开始
            logger.info(f"🌐 [WebAPI] 请求开始: TraceID={trace_id}, IP={client_ip}, 方法={request.method}, 路径={request.url.path}")
            
            # 记录请求参数（如果有）
            if request.query_params:
                logger.debug(f"🔍 [WebAPI] 查询参数: TraceID={trace_id}, 参数={dict(request.query_params)}")
            
            # 3. 继续执行请求
            response: Response = await call_next(request)
            
            # 4. 在响应头中加入 Trace ID
            response.headers["X-Trace-ID"] = trace_id
            
            # 记录请求完成
            process_time = (time.time() - start_time) * 1000
            logger.info(f"✅ [WebAPI] 请求完成: TraceID={trace_id}, IP={client_ip}, 方法={request.method}, 路径={request.url.path}, 状态码={response.status_code}, 耗时={process_time:.2f}ms")
            
            return response
            
        except Exception as e:
            process_time = (time.time() - start_time) * 1000
            # 5. 记录请求失败日志
            logger.error(f"❌ [WebAPI] 请求失败: TraceID={trace_id}, IP={client_ip}, 方法={request.method}, 路径={request.url.path}, 错误={str(e)}, 耗时={process_time:.2f}ms", exc_info=True)
            raise
        finally:
            # 6. 清理上下文
            trace_id_var.reset(token)
