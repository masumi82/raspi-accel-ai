import json
import os


class OfflineBuffer:
    def __init__(self, path):
        self.path = path

    def add(self, event):
        with open(self.path, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def pending(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path) as f:
            return [json.loads(line) for line in f if line.strip()]

    def flush(self, publish_fn):
        items = self.pending()
        sent = 0
        for i, event in enumerate(items):
            try:
                publish_fn(event)
                sent += 1
            except Exception:
                remainder = items[i:]
                with open(self.path, "w") as f:
                    for r in remainder:
                        f.write(json.dumps(r, ensure_ascii=False) + "\n")
                return sent
        if os.path.exists(self.path):
            os.remove(self.path)
        return sent
