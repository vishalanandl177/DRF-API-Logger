import time
from collections import OrderedDict
from threading import Lock


class BoundedRollingState:
    def __init__(self, max_keys=1000, ttl_seconds=300):
        self.max_keys = max_keys
        self.ttl_seconds = ttl_seconds
        self._values = OrderedDict()
        self._lock = Lock()

    def increment(self, key, now=None):
        now = now or time.time()
        with self._lock:
            self._evict_expired(now)
            count, _ = self._values.get(key, (0, now))
            count += 1
            self._values[key] = (count, now)
            self._values.move_to_end(key)
            self._evict_capacity()
            return count

    def get(self, key, now=None):
        now = now or time.time()
        with self._lock:
            self._evict_expired(now)
            count, _ = self._values.get(key, (0, now))
            return count

    def _evict_expired(self, now):
        expired = [
            key
            for key, (_, updated_at) in self._values.items()
            if now - updated_at > self.ttl_seconds
        ]
        for key in expired:
            self._values.pop(key, None)

    def _evict_capacity(self):
        while len(self._values) > self.max_keys:
            self._values.popitem(last=False)
