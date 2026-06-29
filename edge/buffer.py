import json
import os
import tempfile


class OfflineBuffer:
    def __init__(self, path, max_entries=5000):
        self.path = path
        self.max_entries = max_entries

    def add(self, event):
        with open(self.path, "a") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
        items = self.pending()
        if len(items) > self.max_entries:
            self._rewrite(items[-self.max_entries:])

    def pending(self):
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue  # skip corrupt line rather than crash the loop
        return out

    def _rewrite(self, items):
        directory = os.path.dirname(self.path) or "."
        fd, tmp = tempfile.mkstemp(dir=directory)
        try:
            with os.fdopen(fd, "w") as f:
                for item in items:
                    f.write(json.dumps(item, ensure_ascii=False) + "\n")
            os.replace(tmp, self.path)
        except BaseException:
            if os.path.exists(tmp):
                os.remove(tmp)
            raise

    def flush(self, publish_fn):
        items = self.pending()
        sent = 0
        for i, event in enumerate(items):
            try:
                publish_fn(event)
                sent += 1
            except Exception:
                self._rewrite(items[i:])
                return sent
        if os.path.exists(self.path):
            os.remove(self.path)
        return sent
