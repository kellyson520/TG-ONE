import copy

class MessageContext:
    """
    消息上下文类，包含处理消息所需的所有信息
    """
    __slots__ = (
        'client',
        'event',
        'chat_id',
        'rule',
        'trace_id',
        'original_message_text',
        'message_text',
        'check_message_text',
        'media_files',
        'sender_info',
        'time_info',
        'original_link',
        'buttons',
        'should_forward',
        'is_media_group',
        'media_group_id',
        'media_group_messages',
        'skipped_media',
        'errors',
        'forwarded_messages',
        'comment_link',
        # Simulation fields (added in recent tasks)
        'is_sim',
        'trace'
    )
    
    def __init__(self, client, event, chat_id, rule):
        """
        初始化消息上下文
        
        Args:
            client: 机器人客户端
            event: 消息事件
            chat_id: 聊天ID
            rule: 转发规则
        """
        self.client = client
        self.event = event
        self.chat_id = chat_id
        self.rule = rule
        
        # 生成并记录 Trace ID
        from core.context import trace_id_var
        import uuid
        self.trace_id = trace_id_var.get()
        if self.trace_id == "-":
             self.trace_id = uuid.uuid4().hex[:8]
             # 注意：MessageContext 仅仅是数据容器，修改 contextvar 最好在控制流中进行
             # 但为了方便后续逻辑获取，这里也记录一下

        
        # 初始消息文本，保持不变用于引用
        self.original_message_text = event.message.text or ''
        
        # 当前处理的消息文本
        self.message_text = event.message.text or ''
        
        # 用于检查的消息文本（可能包含发送者信息等）
        self.check_message_text = event.message.text or ''
        
        # 记录处理过程中的媒体文件
        self.media_files = []
        
        # 记录发送者信息
        self.sender_info = ''
        
        # 记录时间信息
        self.time_info = ''
        
        # 原始链接
        self.original_link = ''
        
        # 按钮
        self.buttons = event.message.buttons if hasattr(event.message, 'buttons') else None
        
        # 是否继续处理
        self.should_forward = True
        
        # 用于记录媒体组消息
        self.is_media_group = event.message.grouped_id is not None
        self.media_group_id = event.message.grouped_id
        self.media_group_messages = []
        
        # 用于跟踪被跳过的超大媒体
        self.skipped_media = []
        
        # 记录任何可能的错误
        self.errors = []
        
        # 记录已转发的消息
        self.forwarded_messages = []
        
        # 评论区链接
        self.comment_link = None
        
        # Simulation Fields default
        self.is_sim = False
        self.trace = []
        
    def clone(self):
        """创建上下文的副本"""
        return copy.deepcopy(self)
