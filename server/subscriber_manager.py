"""Subscriber registry for the UDP notification server."""

from dataclasses import dataclass
from threading import Lock


@dataclass
class Subscriber:
    client_id: str
    ip: str
    registered_at: float


class SubscriberManager:
    def __init__(self):
        self._subscribers = {}
        self._lock = Lock()

    def register(self, client_id: str, ip: str, registered_at: float) -> Subscriber:
        subscriber = Subscriber(client_id, ip, registered_at)
        with self._lock:
            self._subscribers[client_id] = subscriber
        return subscriber

    def remove(self, client_id: str) -> bool:
        with self._lock:
            return self._subscribers.pop(client_id, None) is not None

    def all(self):
        with self._lock:
            return list(self._subscribers.values())

    def __len__(self):
        with self._lock:
            return len(self._subscribers)
