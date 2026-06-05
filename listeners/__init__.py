"""
统一消息监听模块

该模块提供统一的消息监听接口，使用端口/适配器模式分离框架事件和业务处理。
"""

from .message_listener import setup_listeners

__all__ = ['setup_listeners']
