"""
Lightweight step profiler used across the NL-to-SQL engine.

NOTE: The prototype folder did not contain profiler.py (only a stale compiled .pyc),
so this module is reconstructed from the .pyc interface:
    get_timestamp(), format_duration(seconds), log_step(message, level),
    time_block(step_name, parent_summary, category), CycleProfiler(name).
Set PROFILER_VERBOSE=1 to print step logs; silent by default for service use.
"""
import os
import json
import sys
import time
from contextvars import ContextVar
from threading import Lock
from uuid import uuid4
from contextlib import contextmanager
from datetime import datetime

VERBOSE = os.getenv("PROFILER_VERBOSE", "0").strip() in ("1", "true", "True")
_request_id = ContextVar("nl_sql_request_id", default="-")
_console_lock = Lock()


def trace(stage: str, payload):
    """Print complete process data, without reading environment secrets or headers."""
    rendered = payload if isinstance(payload, str) else json.dumps(payload, indent=2, ensure_ascii=True, default=str)
    encoding = getattr(sys.stdout, "encoding", None) or "utf-8"
    rendered = rendered.encode(encoding, errors="backslashreplace").decode(encoding)
    with _console_lock:
        print(f"\n[{get_timestamp()}] [NL-to-SQL {_request_id.get()}] {stage}\n{rendered}", flush=True)


def begin_trace(endpoint: str, received):
    token = _request_id.set(uuid4().hex[:12])
    trace("RECEIVED INPUT " + endpoint, received)
    return token


def end_trace(token):
    trace("REQUEST END", "Finished processing request.")
    _request_id.reset(token)


def get_timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def format_duration(seconds: float) -> str:
    if seconds < 1.0:
        return f"{seconds * 1000:.1f}ms"
    return f"{seconds:.2f}s"


def log_step(message: str, level: str = "INFO"):
    if _request_id.get() != "-":
        trace(level, message)
        return
    if VERBOSE or level in ("ERROR",):
        print(f"[{get_timestamp()}] [{level}] {message}")


@contextmanager
def time_block(step_name: str, parent_summary: dict = None, category: str = None):
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        if parent_summary is not None and category:
            parent_summary[category] = parent_summary.get(category, 0.0) + duration
        if _request_id.get() != "-":
            trace("TIMER", f"{step_name}: {format_duration(duration)}")
        elif VERBOSE:
            print(f"[{get_timestamp()}] [TIMER] {step_name}: {format_duration(duration)}")


class CycleProfiler:
    def __init__(self, name: str = "Cycle"):
        self.name = name
        self.categories: dict = {}
        self._start = None
        self.total = 0.0

    def start(self):
        self._start = time.perf_counter()

    @contextmanager
    def step(self, step_name: str, category: str = None):
        with time_block(step_name, self.categories, category or step_name):
            yield

    def finish(self):
        if self._start is not None:
            self.total = time.perf_counter() - self._start
        if VERBOSE:
            print(f"[{get_timestamp()}] [PROFILE] {self.name}: {format_duration(self.total)}")
            for cat, dur in sorted(self.categories.items(), key=lambda x: -x[1]):
                print(f"    {cat}: {format_duration(dur)}")
