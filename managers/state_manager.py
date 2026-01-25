class StateManager:
    def __init__(self):
        self._states = {}  # {(user_id, chat_id): "state_name"}

    def set_state(self, user_id, chat_id, state, message=None, state_type=None):
        self._states[(user_id, chat_id)] = state

    def get_state(self, user_id, chat_id):
        return self._states.get((user_id, chat_id)), None, None

    def clear_state(self, user_id, chat_id):
        if (user_id, chat_id) in self._states:
            del self._states[(user_id, chat_id)]
    
    async def clear_state_async(self, user_id, chat_id):
        self.clear_state(user_id, chat_id)

state_manager = StateManager()
