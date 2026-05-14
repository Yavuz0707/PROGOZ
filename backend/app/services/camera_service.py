from typing import Dict

from app.core.camera_stream import CameraStreamWorker


class CameraRuntimeRegistry:
    def __init__(self) -> None:
        self._workers: Dict[int, CameraStreamWorker] = {}

    def start(self, camera_id: int, source: str | int) -> bool:
        if camera_id in self._workers and self._workers[camera_id].running:
            return True
        worker = CameraStreamWorker(camera_id=camera_id, source=source)
        worker.start()
        self._workers[camera_id] = worker
        return True

    def stop(self, camera_id: int) -> bool:
        worker = self._workers.get(camera_id)
        if not worker:
            return False
        worker.stop()
        return True

    def latest_jpeg(self, camera_id: int) -> bytes | None:
        worker = self._workers.get(camera_id)
        return worker.latest_jpeg if worker else None

    def is_running(self, camera_id: int) -> bool:
        worker = self._workers.get(camera_id)
        return bool(worker and worker.running)


camera_runtime = CameraRuntimeRegistry()

