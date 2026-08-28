from pathlib import Path


class PromptService:

    def __init__(self):

        base_dir = Path(__file__).resolve().parent.parent

        prompt_file = base_dir / "prompts" / "cyber_system.txt"

        self.system_prompt = prompt_file.read_text(
            encoding="utf-8"
        )

    def build_messages(self, history, user_message):

        messages = [

            {
                "role": "system",
                "content": self.system_prompt
            }

        ]

        messages.extend(history)

        messages.append(

            {
                "role": "user",
                "content": user_message
            }

        )

        return messages
