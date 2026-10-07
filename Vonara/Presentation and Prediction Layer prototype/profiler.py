"""
Lightweight execution profiler / structured logger.

Mirrors the interface used by Member 1's NL-to-SQL engine so that per-stage
latency numbers from both components can be merged into a single end-to-end
performance table for the research report.
"""

import sys
import time
from contextlib import contextmanager

VERBOSE = True

_LEVEL_TAGS = {
    "INFO": "INFO ",
    "WARN": "WARN ",
    "ERROR": "ERROR",
    "DEBUG": "DEBUG",
}


def log_step(message: str, level: str = "INFO") -> None:
    """Emit a single structured log line to stderr."""
    if not VERBOSE and level.upper() == "DEBUG":
        return
    tag = _LEVEL_TAGS.get(level.upper(), "INFO ")
    print(f"[{tag}] {message}", file=sys.stderr)


@contextmanager
def time_block(label: str, parent_summary: dict = None, category: str = "General"):
    """
    Context manager timing a block of work.

    If `parent_summary` (a dict) is supplied, elapsed milliseconds accumulate
    under `category`, letting a Profiler report totals per pipeline stage.
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        if parent_summary is not None:
            parent_summary[category] = parent_summary.get(category, 0.0) + elapsed_ms
        log_step(f"{label} completed in {elapsed_ms:.1f} ms", level="DEBUG")


class Profiler:
    """Accumulates per-category timings across a full pipeline execution."""

    def __init__(self, name: str = "pipeline"):
        self.name = name
        self.categories: dict = {}
        self._started = time.perf_counter()

    def stage(self, label: str, category: str):
        """Return a timing context manager bound to this profiler."""
        return time_block(label, parent_summary=self.categories, category=category)

    @property
    def total_ms(self) -> float:
        return (time.perf_counter() - self._started) * 1000.0

    def report(self) -> dict:
        """Return a JSON-serialisable timing breakdown."""
        return {
            "total_execution_ms": round(self.total_ms, 2),
            "stage_breakdown_ms": {
                k: round(v, 2)
                for k, v in sorted(self.categories.items(), key=lambda kv: -kv[1])
            },
        }

    def print_report(self) -> None:
        rep = self.report()
        log_step(f"--- Profiler report: {self.name} ---")
        for stage, ms in rep["stage_breakdown_ms"].items():
            log_step(f"  {stage:<38} {ms:>8.2f} ms")
        log_step(f"  {'TOTAL':<38} {rep['total_execution_ms']:>8.2f} ms")
