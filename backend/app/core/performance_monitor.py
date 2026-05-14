from collections import deque
from time import perf_counter


class PerformanceMonitor:
    def __init__(self, window: int = 30) -> None:
        self.window = deque(maxlen=window)
        self.started = perf_counter()

    def tick(self, latency_ms: float = 0.0) -> dict:
        now = perf_counter()
        self.window.append(now)
        fps = 0.0
        if len(self.window) >= 2:
            fps = (len(self.window) - 1) / max(self.window[-1] - self.window[0], 1e-6)
        return {"fps": round(fps, 2), "latency_ms": round(latency_ms, 1)}

