from collections import defaultdict


class MemoryService:

    def __init__(self):

        self.sessions = defaultdict(list)

        self.max_messages = 20

    def get_history(self, session_id: str):

        return self.sessions.get(session_id, [])

    def add_user_message(self, session_id: str, message: str):

        self.sessions[session_id].append(
            {
                "role": "user",
                "content": message
            }
        )

        self._trim(session_id)

    def add_assistant_message(self, session_id: str, message: str):

        self.sessions[session_id].append(
            {
                "role": "assistant",
                "content": message
            }
        )

        self._trim(session_id)

    def clear(self, session_id: str):

        self.sessions.pop(session_id, None)

    def _trim(self, session_id):

        if len(self.sessions[session_id]) > self.max_messages:

            self.sessions[session_id] = self.sessions[session_id][-self.max_messages:]
