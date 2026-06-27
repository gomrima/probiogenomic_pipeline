#!/usr/bin/env python3

import sys
import time


class TerminalProgress:
    def __init__(self, total: int, prefix: str = "PROGRESS", unicode_blocks: bool = False, width: int = 20):
        self.total = max(int(total), 1)
        self.prefix = prefix
        self.width = width
        self.fill = "#" if not unicode_blocks else "#"
        self.empty = "-" if not unicode_blocks else " "
        self.start = time.time()

    @staticmethod
    def _fmt(seconds: float) -> str:
        seconds = int(max(seconds, 0))
        hours, rem = divmod(seconds, 3600)
        minutes, sec = divmod(rem, 60)
        return f"{hours:02d}:{minutes:02d}:{sec:02d}"

    def update(self, current: int, active_item: str = "") -> None:
        current = min(max(int(current), 0), self.total)
        frac = current / self.total
        elapsed = time.time() - self.start
        rate = current / elapsed if elapsed > 0 and current > 0 else 0.0
        remaining = (self.total - current) / rate if rate > 0 else 0.0
        filled = int(self.width * frac)
        bar = self.fill * filled + self.empty * (self.width - filled)
        line = (
            f"[{self.prefix}] [{bar}] {frac * 100:5.1f} percent | "
            f"{current}/{self.total} | elapsed {self._fmt(elapsed)} | "
            f"eta {self._fmt(remaining)} | active {active_item}"
        )
        sys.stdout.write("\r" + line)
        sys.stdout.flush()
        if current >= self.total:
            sys.stdout.write("\n")
            sys.stdout.flush()

