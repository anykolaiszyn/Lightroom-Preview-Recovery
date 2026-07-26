from __future__ import annotations

import threading
import time
import tkinter as tk
from pathlib import Path

import pytest

import lightroom_preview_recovery.gui as gui
import lightroom_preview_recovery.worker as worker_module
from lightroom_preview_recovery.models import (
    PreflightResult,
    RecoveryConfig,
    RecoverySummary,
)
from lightroom_preview_recovery.worker import (
    ProgressSnapshot,
    RecoveryWorker,
    WorkerMessage,
)


def _window_gone(instance: tk.Misc) -> bool:
    try:
        return not instance.winfo_exists()
    except tk.TclError:
        return True


@pytest.fixture
def window() -> gui.MainWindow:
    instance = gui.MainWindow()
    instance.withdraw()
    yield instance
    if not _window_gone(instance):
        instance.destroy()
        _pump_until(instance, lambda: _window_gone(instance), timeout=5.0)


def _ready(window: gui.MainWindow, tmp_path: Path) -> None:
    window.catalog_var.set(str(tmp_path / "Catalog.lrcat"))
    window.previews_var.set(str(tmp_path / "Catalog Previews.lrdata"))
    window.output_var.set(str(tmp_path / "Recovered"))
    window.update_idletasks()


def _preflight(
    *, errors: tuple[str, ...] = (), warnings: tuple[str, ...] = (), count: int = 2
) -> PreflightResult:
    return PreflightResult(errors, warnings, count, count, 0)


def _enabled(widget: tk.Widget) -> bool:
    return "disabled" not in widget.state()


def _pump_until(
    window: tk.Misc,
    predicate,
    *,
    timeout: float = 3.0,
) -> None:
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() >= deadline:
            raise AssertionError("timed out waiting for tkinter event")
        window.update()
        time.sleep(0.005)


def test_start_disabled_until_all_paths_are_selected(
    window: gui.MainWindow, tmp_path: Path
) -> None:
    assert not _enabled(window.start_button)
    _ready(window, tmp_path)
    assert _enabled(window.start_button)


def test_preview_and_output_browse_use_directory_picker(
    window: gui.MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    selected = iter(
        (
            str(tmp_path / "Catalog Previews.lrdata"),
            str(tmp_path / "Destination"),
        )
    )
    monkeypatch.setattr(gui.filedialog, "askdirectory", lambda **_: next(selected))
    monkeypatch.setattr(
        gui.filedialog,
        "askopenfilename",
        lambda **_: pytest.fail("directory fields must not use a file picker"),
    )

    window.previews_browse.invoke()
    window.output_browse.invoke()

    assert window.previews_var.get().endswith("Catalog Previews.lrdata")
    assert window.output_var.get().endswith("Destination")


def test_catalog_browse_uses_lrcat_file_picker(
    window: gui.MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    selected = str(tmp_path / "Lightroom Catalog.lrcat")
    monkeypatch.setattr(
        gui.filedialog, "askopenfilename", lambda **_: selected
    )

    window.catalog_browse.invoke()

    assert window.catalog_var.get() == selected


def test_preflight_error_blocks_start_and_explains_remedy(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _ready(window, tmp_path)
    monkeypatch.setattr(
        gui,
        "run_preflight",
        lambda _: _preflight(
            errors=("Output parent is inside the preview source.",)
        ),
    )

    window.start_button.invoke()

    assert window._worker is None
    assert "cannot start" in window.status_var.get().lower()
    assert "inside" in window.activity.get("1.0", "end").lower()
    assert _enabled(window.start_button)


def test_preflight_warning_is_visible_before_worker_start(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _ready(window, tmp_path)
    monkeypatch.setattr(
        gui, "run_preflight", lambda _: _preflight(warnings=("Count mismatch.",))
    )
    seen: list[str] = []
    monkeypatch.setattr(window, "_start_worker", lambda _: seen.append("started"))

    window.start_button.invoke()

    assert "count mismatch" in window.activity.get("1.0", "end").lower()
    assert seen == ["started"]


def test_preflight_exception_restores_usable_window(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _ready(window, tmp_path)
    monkeypatch.setattr(
        gui,
        "run_preflight",
        lambda _: (_ for _ in ()).throw(OSError("catalog cannot be read")),
    )

    window.start_button.invoke()

    assert window._worker is None
    assert window._elapsed_after_id is None
    assert _enabled(window.catalog_entry)
    assert _enabled(window.start_button)
    assert "could not check" in window.status_var.get().lower()
    assert "catalog cannot be read" in window.activity.get("1.0", "end").lower()


def test_worker_start_exception_restores_controls(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class RaisingWorker:
        def __init__(self, config: RecoveryConfig) -> None:
            self.config = config

        def start(self) -> None:
            raise RuntimeError("thread unavailable")

        def cancel(self) -> None:
            pass

        def join(self, timeout: float | None = None) -> None:
            pass

        @property
        def is_running(self) -> bool:
            return False

        def drain_messages(self) -> list[WorkerMessage]:
            return []

    _ready(window, tmp_path)
    monkeypatch.setattr(gui, "run_preflight", lambda _: _preflight())
    monkeypatch.setattr(gui, "RecoveryWorker", RaisingWorker)

    window.start_button.invoke()

    assert window._worker is None
    assert window._poll_after_id is None
    assert window._elapsed_after_id is None
    assert _enabled(window.catalog_entry)
    assert _enabled(window.start_button)
    assert "could not start" in window.status_var.get().lower()


def test_zero_preview_preflight_keeps_exact_zero_progress_maximum(
    window: gui.MainWindow,
) -> None:
    window._reset_run_display(0)
    assert float(window.progress.cget("maximum")) == 0
    assert "no previews" in window.progress_help_var.get().lower()


def test_worker_emits_detached_scalar_progress_and_full_completion(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    caller_thread = threading.get_ident()
    observed_thread: list[int] = []

    class Coordinator:
        def run(self, config, cancel_event, on_progress):
            observed_thread.append(threading.get_ident())
            shared = RecoverySummary(examined=1, recovered=1)
            shared.results.append(object())  # type: ignore[arg-type]
            on_progress(shared, object())
            shared.examined = 2
            shared.recovered = 2
            shared.results.append(object())  # type: ignore[arg-type]
            on_progress(shared, object())
            shared.examined = 99
            return shared

    monkeypatch.setattr(worker_module, "RecoveryCoordinator", Coordinator)
    worker = RecoveryWorker(
        RecoveryConfig(tmp_path / "a.lrcat", tmp_path / "p", tmp_path / "o")
    )

    worker.start()
    worker.join(3)
    messages = worker.drain_messages()

    progress = [
        message.payload
        for message in messages
        if message.kind == "progress"
    ]
    completed = next(
        message.payload for message in messages if message.kind == "completed"
    )
    assert observed_thread[0] != caller_thread
    assert progress == [
        ProgressSnapshot(1, 1, 0, 0, 0),
        ProgressSnapshot(2, 2, 0, 0, 0),
    ]
    assert completed.examined == 99
    assert len(completed.results) == 2
    assert not worker.is_running


def test_background_worker_updates_gui_only_when_queue_is_polled(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class Coordinator:
        def run(self, config, cancel_event, on_progress):
            summary = RecoverySummary(examined=1, recovered=1)
            on_progress(summary, object())
            return summary

    monkeypatch.setattr(worker_module, "RecoveryCoordinator", Coordinator)
    monkeypatch.setattr(gui, "run_preflight", lambda _: _preflight(count=1))
    _ready(window, tmp_path)

    window.start_button.invoke()
    assert window.counter_vars["examined"].get() == "0"
    _pump_until(window, lambda: window._worker is None)

    assert window.counter_vars["examined"].get() == "1"
    assert "complete" in window.status_var.get().lower()
    assert window._elapsed_after_id is None


def test_cancel_and_close_waits_for_real_worker_without_leaving_thread(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class Coordinator:
        def run(self, config, cancel_event, on_progress):
            summary = RecoverySummary()
            while not cancel_event.wait(0.005):
                pass
            summary.cancelled = True
            return summary

    monkeypatch.setattr(worker_module, "RecoveryCoordinator", Coordinator)
    monkeypatch.setattr(gui, "run_preflight", lambda _: _preflight(count=1))
    _ready(window, tmp_path)
    window.start_button.invoke()
    worker = window._worker
    assert worker is not None
    _pump_until(window, lambda: worker.is_running)

    window._request_close()
    _pump_until(window, lambda: not worker.is_running)
    _pump_until(window, lambda: window._destroyed)

    assert not worker.is_running
    assert window._worker is None


def test_close_during_run_fully_tears_down_tk_root_for_fixture_reuse(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A synchronous destroy() call must not leave the interpreter half-alive.

    ``_final_destroy`` defers real teardown via ``after_idle`` while a worker
    thread is still running, so a single synchronous ``destroy()`` call (as
    the ``window`` fixture used to make) can return before the Tk root is
    actually gone -- corrupting whichever test creates the next ``tk.Tk()``
    in this process. This proves the pump-until-gone sequence the fixture now
    uses actually reaches a fully destroyed, thread-free state.
    """
    thread_alive_after_destroy: list[bool] = []

    class Coordinator:
        def run(self, config, cancel_event, on_progress):
            summary = RecoverySummary()
            while not cancel_event.wait(0.005):
                pass
            summary.cancelled = True
            return summary

    monkeypatch.setattr(worker_module, "RecoveryCoordinator", Coordinator)
    monkeypatch.setattr(gui, "run_preflight", lambda _: _preflight(count=1))
    _ready(window, tmp_path)
    window.start_button.invoke()
    worker = window._worker
    assert worker is not None
    _pump_until(window, lambda: worker.is_running)

    window.destroy()
    _pump_until(window, lambda: _window_gone(window), timeout=5.0)
    thread_alive_after_destroy.append(worker.is_running)

    assert _window_gone(window)
    assert thread_alive_after_destroy == [False]

    fresh = gui.MainWindow()
    try:
        fresh.withdraw()
        fresh.update_idletasks()
    finally:
        fresh.destroy()


def test_failure_stops_timer_and_restores_controls(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class Coordinator:
        def run(self, config, cancel_event, on_progress):
            raise RuntimeError("disk unavailable")

    monkeypatch.setattr(worker_module, "RecoveryCoordinator", Coordinator)
    monkeypatch.setattr(gui, "run_preflight", lambda _: _preflight())
    _ready(window, tmp_path)

    window.start_button.invoke()
    _pump_until(window, lambda: window._worker is None)

    assert "failed" in window.status_var.get().lower()
    assert "disk unavailable" in window.activity.get("1.0", "end").lower()
    assert window._elapsed_after_id is None
    assert _enabled(window.catalog_entry)


def test_open_actions_require_existing_directory_and_report(
    window: gui.MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    window._output_root = tmp_path / "Recovered Lightroom Previews"
    window._report_path = window._output_root / "recovery-report.html"
    opened: list[Path] = []
    monkeypatch.setattr(gui, "_open_local_path", opened.append)

    window._refresh_open_actions()
    window.open_output_button.invoke()
    window.open_report_button.invoke()
    assert not _enabled(window.open_output_button)
    assert not _enabled(window.open_report_button)
    assert opened == []

    window._output_root.mkdir()
    window._report_path.write_text("report", encoding="utf-8")
    window._refresh_open_actions()
    window.open_output_button.invoke()
    window.open_report_button.invoke()

    assert opened == [window._output_root, window._report_path]


def test_elapsed_timer_uses_hours_minutes_seconds(
    window: gui.MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(gui.time, "monotonic", lambda: 3_661.9)
    window._started_at = 0.0
    window._update_elapsed()
    assert window.elapsed_var.get() == "Elapsed  01:01:01"


def test_coffee_link_opens_support_page(
    window: gui.MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(gui.webbrowser, "open", opened.append)

    window.coffee_link.invoke()

    assert opened == [gui.COFFEE_URL]


def test_splash_screen_auto_dismisses_and_reports_done() -> None:
    splash = gui.SplashScreen(display_ms=1)
    splash.withdraw()
    finished: list[bool] = []
    splash.on_dismiss(lambda: finished.append(True))

    _pump_until(splash, lambda: bool(finished), timeout=3.0)

    assert finished == [True]
    _pump_until(splash, lambda: _window_gone(splash), timeout=3.0)


def test_splash_screen_dismisses_immediately_on_click() -> None:
    splash = gui.SplashScreen(display_ms=10_000)
    splash.withdraw()
    finished: list[bool] = []
    splash.on_dismiss(lambda: finished.append(True))

    splash.event_generate("<Button-1>")

    _pump_until(splash, lambda: bool(finished), timeout=3.0)
    assert finished == [True]
