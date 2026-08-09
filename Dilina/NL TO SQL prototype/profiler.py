import time
from datetime import datetime
from contextlib import contextmanager

def get_timestamp() -> str:
    """Returns current time formatted as HH:MM:SS.mmm"""
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]

def format_duration(seconds: float) -> str:
    """Formats duration in seconds or milliseconds for high readability."""
    if seconds < 0.001:
        return f"{seconds * 1_000_000:.1f}us"
    elif seconds < 1.0:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds:.3f}s"

def log_step(message: str, level: str = "INFO"):
    """Logs a micro-step event with exact timestamp."""
    print(f"[{get_timestamp()}] [{level}] {message}")

@contextmanager
def time_block(step_name: str, parent_summary: dict = None, category: str = None):
    """
    Context manager to time a micro-step.
    Prints start, completion duration, and records elapsed time in parent_summary dictionary if provided.
    """
    start_time = time.perf_counter()
    ts_start = get_timestamp()
    print(f"[{ts_start}] [START] {step_name}...")
    
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start_time
        ts_end = get_timestamp()
        duration_str = format_duration(elapsed)
        print(f"[{ts_end}] [DONE]  {step_name} ({duration_str})")
        
        if parent_summary is not None and category:
            parent_summary[category] = parent_summary.get(category, 0.0) + elapsed

class CycleProfiler:
    """
    Tracks and aggregates timing for a full execution cycle.
    """
    def __init__(self, cycle_name: str = "NL-to-SQL Cycle"):
        self.cycle_name = cycle_name
        self.start_time = None
        self.categories = {}
        
    def start(self):
        self.start_time = time.perf_counter()
        log_step(f"Starting {self.cycle_name}", level="CYCLE")

    @contextmanager
    def step(self, step_name: str, category: str = None):
        cat = category or step_name
        with time_block(step_name, self.categories, cat):
            yield

    def finish(self):
        total_time = time.perf_counter() - self.start_time if self.start_time else 0.0
        print("\n" + "=" * 60)
        print(f"       TIMING BREAKDOWN SUMMARY ({self.cycle_name})")
        print("=" * 60)
        print(f" Total Cycle Time: {format_duration(total_time)}")
        print("-" * 60)
        
        if self.categories:
            sorted_cats = sorted(self.categories.items(), key=lambda x: x[1], reverse=True)
            for cat, duration in sorted_cats:
                pct = (duration / total_time * 100) if total_time > 0 else 0
                bar = "=" * int(pct / 5)
                print(f" * {cat:<35} : {format_duration(duration):>10} ({pct:5.1f}%) {bar}")
        print("=" * 60 + "\n")

