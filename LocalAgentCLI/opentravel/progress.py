from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import TextIO

import sys


@dataclass
class ProgressReporter:
    enabled: bool = True
    language: str = "zh"
    stream: TextIO = sys.stderr

    def __post_init__(self) -> None:
        self._started = monotonic()

    def log(self, message: str, percent: int | None = None) -> None:
        if not self.enabled:
            return
        elapsed = monotonic() - self._started
        prefix = f"[{percent:>3}%]" if percent is not None else "[ --- ]"
        print(f"{prefix} {message} (+{elapsed:.1f}s)", file=self.stream, flush=True)

    def stage(self, message: str, percent: int | None = None) -> None:
        self.log(message, percent=percent)

    def day(self, current: int, total: int, message: str) -> None:
        if total <= 0:
            self.log(message)
            return
        percent = int(current * 100 / total)
        self.log(f"{message} ({current}/{total})", percent=percent)

