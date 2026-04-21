from __future__ import annotations

from dataclasses import dataclass
from typing import TextIO

import sys


@dataclass
class ProgressReporter:
    enabled: bool = True
    language: str = "zh"
    stream: TextIO = sys.stderr

    def __post_init__(self) -> None:
        return

    def log(self, message: str, percent: int | None = None) -> None:
        if not self.enabled:
            return
        prefix = f"[{percent:>3}%]" if percent is not None else "[ --- ]"
        print(f"{prefix} {message}", file=self.stream, flush=True)

    def stage(self, message: str, percent: int | None = None) -> None:
        self.log(message, percent=percent)

    def day(self, current: int, total: int, message: str) -> None:
        if total <= 0:
            self.log(message)
            return
        percent = int(current * 100 / total)
        self.log(f"{message} ({current}/{total})", percent=percent)

