import json
import os

class EmbedStateManager:
    def __init__(self, filename="embed_state.json"):
        self.path = os.path.join(os.path.dirname(__file__), filename)
        self.state = self._load()

    def _load(self):
        if os.path.exists(self.path):
            try:
                with open(self.path, "r") as f:
                    return json.load(f)
            except: pass
        return {}

    def save(self):
        with open(self.path, "w") as f:
            json.dump(self.state, f)

    def save_message_id(self, key, message_id):
        self.state[f"msg_{key}"] = message_id
        self.save()

    def load_message_id(self, key):
        return self.state.get(f"msg_{key}")

    def save_value(self, key, value):
        self.state[key] = value
        self.save()

    def load_value(self, key, default=None):
        return self.state.get(key, default)
