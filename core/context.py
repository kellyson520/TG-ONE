import contextvars

# Global context var for Trace ID
trace_id_var = contextvars.ContextVar("trace_id", default="-")

# Security Context Vars
request_id_var = contextvars.ContextVar("request_id", default="unknown")
user_id_var = contextvars.ContextVar("user_id", default=None)
username_var = contextvars.ContextVar("username", default="anonymous")
ip_address_var = contextvars.ContextVar("ip_address", default="unknown")
user_agent_var = contextvars.ContextVar("user_agent", default="unknown")
