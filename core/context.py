import contextvars

# Global context var for Trace ID
trace_id_var = contextvars.ContextVar("trace_id", default="-")
