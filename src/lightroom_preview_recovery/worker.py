from __future__ import annotations

from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Lock, Thread
from typing import Literal

from .models import RecoveryConfig, RecoverySummary
from .recovery import RecoveryCoordinator


@dataclass(frozen=True, slots=True)
class ProgressSnapshot:
    """The scalar recovery state needed by the interface."""

    examined: int
    recovered: int
    unmapped: int
    skipped: int
    failed: int


WorkerMessageKind = Literal["progress", "completed", "failed", "finished"]


@dataclass(frozen=True, slots=True)
class WorkerMessage:
    kind: WorkerMessageKind
    payload: object | None = None


class RecoveryWorker:
    """Run the recovery coordinator without any dependency on a GUI toolkit."""

    def __init__(self, config: RecoveryConfig) -> None:
        self.config = config
        self.cancel_event = Event()
        self._messages: Queue[WorkerMessage] = Queue()
        self._thread: Thread | None = None
        self._start_lock = Lock()

    def start(self) -> None:
        with self._start_lock:
            if self._thread is not None:
                raise RuntimeError("recovery worker has already been started")
            thread = Thread(
                target=self._run,
                name="Lightroom preview recovery",
                daemon=False,
            )
            self._thread = thread
            thread.start()

    def cancel(self) -> None:
        self.cancel_event.set()

    def join(self, timeout: float | None = None) -> None:
        thread = self._thread
        if thread is not None:
            thread.join(timeout)

    @property
    def is_running(self) -> bool:
        thread = self._thread
        return thread is not None and thread.is_alive()

    def drain_messages(self) -> list[WorkerMessage]:
        messages: list[WorkerMessage] = []
        while True:
            try:
                messages.append(self._messages.get_nowait())
            except Empty:
                return messages

    def _run(self) -> None:
        try:
            summary = RecoveryCoordinator().run(
                self.config,
                self.cancel_event,
                self._publish_progress,
            )
            self._messages.put(WorkerMessage("completed", summary))
        except Exception as error:
            self._messages.put(
                WorkerMessage("failed", f"{type(error).__name__}: {error}")
            )
        finally:
            self._messages.put(WorkerMessage("finished"))

    def _publish_progress(
        self, summary: RecoverySummary, _entry: object
    ) -> None:
        snapshot = ProgressSnapshot(
            examined=summary.examined,
            recovered=summary.recovered,
            unmapped=summary.unmapped,
            skipped=summary.skipped,
            failed=summary.failed,
        )
        self._messages.put(WorkerMessage("progress", snapshot))
