"""Fan-out with dedup and a recorded retry. Failed channels do not raise into the signal."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Delivery:
    channel: str
    signal_id: str
    category: str
    status: str
    attempts: int


class RecordingChannel:
    def __init__(self, name: str, *, fail_times: int = 0) -> None:
        self.name = name
        self.fail_times = fail_times
        self.sent: list[tuple[str, str]] = []

    def send(self, signal_id: str, category: str, body: str) -> None:
        if self.fail_times > 0:
            self.fail_times -= 1
            raise ConnectionError(self.name)
        self.sent.append((signal_id, body))


@dataclass
class Dispatcher:
    channels: list[RecordingChannel]
    deliveries: list[Delivery] = field(default_factory=list)
    _sent_keys: set[tuple[str, str, str]] = field(default_factory=set)

    def notify(self, signal_id: str, category: str, body: str) -> list[Delivery]:
        results: list[Delivery] = []
        for channel in self.channels:
            key = (channel.name, signal_id, category)
            if key in self._sent_keys:
                results.append(Delivery(channel.name, signal_id, category, "duplicate_suppressed", 0))
                continue
            attempts = 0
            status = "failed"
            while attempts < 2:
                attempts += 1
                try:
                    channel.send(signal_id, category, body)
                    status = "sent"
                    self._sent_keys.add(key)
                    break
                except ConnectionError:
                    status = "failed"
            delivery = Delivery(channel.name, signal_id, category, status, attempts)
            self.deliveries.append(delivery)
            results.append(delivery)
        return results
