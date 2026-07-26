from __future__ import annotations

import os
import time
import tkinter as tk
import webbrowser
from collections.abc import Callable
from pathlib import Path
from tkinter import filedialog, ttk

from .models import PreflightResult, RecoveryConfig, RecoverySummary
from .preflight import run_preflight
from .worker import ProgressSnapshot, RecoveryWorker, WorkerMessage


_PAPER = "#F4F5F2"
_SURFACE = "#FFFFFF"
_GRAPHITE = "#17212B"
_SLATE = "#66737F"
_LINE = "#CDD4D8"
_CYAN = "#2D7E91"
_CYAN_PALE = "#E8EFF0"
_ACTIVITY_TEXT = "#E5EEF0"

COFFEE_URL = "https://buymeacoffee.com/alexnyk"


def _open_local_path(path: Path) -> None:
    """Ask the operating system to open a local directory or report."""
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
        return
    webbrowser.open(path.resolve().as_uri())


class MainWindow(tk.Tk):
    """A quiet, Windows-friendly interface for recovering cached previews."""

    _POLL_MILLISECONDS = 35

    def __init__(self) -> None:
        super().__init__()
        self._worker: RecoveryWorker | None = None
        self._active_preflight: PreflightResult | None = None
        self._output_root: Path | None = None
        self._report_path: Path | None = None
        self._poll_after_id: str | None = None
        self._elapsed_after_id: str | None = None
        self._started_at: float | None = None
        self._terminal_received = False
        self._worker_finished_seen = False
        self._close_requested = False
        self._destroyed = False

        self.title("Lightroom Preview Recovery")
        self.geometry("840x700")
        self.minsize(760, 620)
        self.configure(background=_PAPER)
        self.protocol("WM_DELETE_WINDOW", self._request_close)

        self._configure_style()
        self._build_ui()
        self._bind_shortcuts()
        self._update_start_enabled()

    def _configure_style(self) -> None:
        style = ttk.Style(self)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure(".", font=("Segoe UI", 10))
        style.configure("Paper.TFrame", background=_PAPER)
        style.configure("Surface.TFrame", background=_SURFACE)
        style.configure(
            "Eyebrow.TLabel",
            background=_PAPER,
            foreground=_CYAN,
            font=("Segoe UI", 9, "bold"),
        )
        style.configure(
            "Title.TLabel",
            background=_PAPER,
            foreground=_GRAPHITE,
            font=("Georgia", 25, "bold"),
        )
        style.configure(
            "Body.TLabel",
            background=_PAPER,
            foreground=_SLATE,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Status.TLabel",
            background=_CYAN_PALE,
            foreground=_GRAPHITE,
            padding=(12, 9),
        )
        style.configure(
            "Panel.TLabelframe",
            background=_PAPER,
            bordercolor=_LINE,
            relief="solid",
        )
        style.configure(
            "Panel.TLabelframe.Label",
            background=_PAPER,
            foreground=_GRAPHITE,
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "CounterName.TLabel",
            background=_SURFACE,
            foreground=_SLATE,
            font=("Segoe UI", 9),
        )
        style.configure(
            "CounterValue.TLabel",
            background=_SURFACE,
            foreground=_GRAPHITE,
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Dark.TButton",
            background=_GRAPHITE,
            foreground=_GRAPHITE,
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.map(
            "Dark.TButton",
            foreground=[("disabled", _SLATE), ("!disabled", _GRAPHITE)],
        )
        style.configure(
            "Recovery.Horizontal.TProgressbar",
            troughcolor="#E1E5E5",
            background=_CYAN,
            bordercolor=_SURFACE,
            lightcolor=_CYAN,
            darkcolor=_CYAN,
            thickness=11,
        )
        style.configure(
            "Coffee.TButton",
            background=_PAPER,
            foreground=_SLATE,
            padding=(0, 4),
            font=("Segoe UI", 9),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Coffee.TButton",
            foreground=[("active", _CYAN), ("!active", _SLATE)],
        )

    def _build_ui(self) -> None:
        root = ttk.Frame(self, style="Paper.TFrame", padding=(28, 23))
        root.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        root.columnconfigure(0, weight=1)
        root.rowconfigure(8, weight=1)

        ttk.Label(
            root,
            text="LIGHTROOM CLASSIC  /  PREVIEW CACHE",
            style="Eyebrow.TLabel",
        ).grid(row=0, column=0, sticky="w")

        heading = ttk.Frame(root, style="Paper.TFrame")
        heading.grid(row=1, column=0, sticky="ew", pady=(4, 3))
        heading.columnconfigure(0, weight=1)
        ttk.Label(
            heading, text="Preview recovery", style="Title.TLabel"
        ).grid(row=0, column=0, sticky="w")
        self.elapsed_var = tk.StringVar(value="Elapsed  00:00:00")
        ttk.Label(
            heading, textvariable=self.elapsed_var, style="Body.TLabel"
        ).grid(row=0, column=1, sticky="e")

        ttk.Label(
            root,
            text=(
                "Recover cached JPEG previews from a Lightroom backup. "
                "Your catalog and preview cache are read-only and remain unchanged."
            ),
            style="Body.TLabel",
            wraplength=760,
        ).grid(row=2, column=0, sticky="ew", pady=(0, 13))

        source = ttk.LabelFrame(
            root, text="Choose backup", style="Panel.TLabelframe", padding=12
        )
        source.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        source.columnconfigure(1, weight=1)
        self.catalog_var = tk.StringVar()
        self.previews_var = tk.StringVar()
        self.catalog_entry, self.catalog_browse = self._path_row(
            source,
            row=0,
            label="Catalog (.lrcat)",
            variable=self.catalog_var,
            browse=self._choose_catalog,
            mnemonic=0,
        )
        self.previews_entry, self.previews_browse = self._path_row(
            source,
            row=1,
            label="Preview cache (.lrdata)",
            variable=self.previews_var,
            browse=self._choose_previews,
            mnemonic=0,
        )

        destination = ttk.LabelFrame(
            root,
            text="Save recovered previews",
            style="Panel.TLabelframe",
            padding=12,
        )
        destination.grid(row=4, column=0, sticky="ew", pady=(0, 10))
        destination.columnconfigure(1, weight=1)
        self.output_var = tk.StringVar()
        self.output_entry, self.output_browse = self._path_row(
            destination,
            row=0,
            label="Destination folder",
            variable=self.output_var,
            browse=self._choose_output,
            mnemonic=0,
        )
        ttk.Label(
            destination,
            text="A “Recovered Lightroom Previews” folder will be created there.",
            foreground=_SLATE,
        ).grid(row=1, column=1, columnspan=2, sticky="w", pady=(3, 0))

        for variable in (self.catalog_var, self.previews_var, self.output_var):
            variable.trace_add("write", self._paths_changed)

        self.status_var = tk.StringVar(
            value="Choose the backup and a separate destination to begin."
        )
        ttk.Label(
            root,
            textvariable=self.status_var,
            style="Status.TLabel",
            wraplength=760,
        ).grid(row=5, column=0, sticky="ew", pady=(0, 10))

        progress_panel = ttk.Frame(
            root, style="Surface.TFrame", padding=(14, 12)
        )
        progress_panel.grid(row=6, column=0, sticky="ew", pady=(0, 10))
        progress_panel.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(
            progress_panel,
            mode="determinate",
            maximum=1,
            value=0,
            style="Recovery.Horizontal.TProgressbar",
        )
        self.progress.grid(row=0, column=0, sticky="ew")
        self.progress_help_var = tk.StringVar(
            value="Recovery has not started."
        )
        ttk.Label(
            progress_panel,
            textvariable=self.progress_help_var,
            style="CounterName.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 5))

        counters = ttk.Frame(progress_panel, style="Surface.TFrame")
        counters.grid(row=2, column=0, sticky="ew")
        self.counter_vars: dict[str, tk.StringVar] = {}
        for index, name in enumerate(
            ("examined", "recovered", "unmapped", "skipped", "failed")
        ):
            counters.columnconfigure(index, weight=1)
            cell = ttk.Frame(counters, style="Surface.TFrame")
            cell.grid(row=0, column=index, sticky="ew", padx=(0, 14))
            ttk.Label(
                cell, text=name.capitalize(), style="CounterName.TLabel"
            ).grid(row=0, column=0, sticky="w")
            value = tk.StringVar(value="0")
            ttk.Label(
                cell, textvariable=value, style="CounterValue.TLabel"
            ).grid(row=1, column=0, sticky="w")
            self.counter_vars[name] = value

        actions = ttk.Frame(root, style="Paper.TFrame")
        actions.grid(row=7, column=0, sticky="ew", pady=(0, 10))
        actions.columnconfigure(2, weight=1)
        self.start_button = ttk.Button(
            actions,
            text="Start recovery",
            command=self._start_recovery,
            style="Dark.TButton",
            underline=0,
        )
        self.cancel_button = ttk.Button(
            actions,
            text="Cancel",
            command=self._request_cancel,
            underline=0,
        )
        self.open_output_button = ttk.Button(
            actions,
            text="Open output",
            command=self._open_output,
            underline=5,
        )
        self.open_report_button = ttk.Button(
            actions,
            text="Open report",
            command=self._open_report,
            underline=5,
        )
        self.start_button.grid(row=0, column=0, padx=(0, 8))
        self.cancel_button.grid(row=0, column=1)
        self.open_output_button.grid(row=0, column=3, padx=(8, 0))
        self.open_report_button.grid(row=0, column=4, padx=(8, 0))
        self._set_enabled(self.cancel_button, False)
        self._set_enabled(self.open_output_button, False)
        self._set_enabled(self.open_report_button, False)

        self.activity = tk.Text(
            root,
            height=8,
            wrap="word",
            background=_GRAPHITE,
            foreground=_ACTIVITY_TEXT,
            insertbackground=_ACTIVITY_TEXT,
            relief="flat",
            borderwidth=0,
            padx=11,
            pady=9,
            font=("Consolas", 9),
            state="disabled",
            takefocus=True,
        )
        self.activity.grid(row=8, column=0, sticky="nsew")

        footer = ttk.Frame(root, style="Paper.TFrame")
        footer.grid(row=9, column=0, sticky="e", pady=(6, 0))
        self.coffee_link = ttk.Button(
            footer,
            text="☕ Buy me a coffee",
            command=self._open_coffee_link,
            style="Coffee.TButton",
            cursor="hand2",
        )
        self.coffee_link.grid(row=0, column=0)

        self._selector_widgets = (
            self.catalog_entry,
            self.previews_entry,
            self.output_entry,
            self.catalog_browse,
            self.previews_browse,
            self.output_browse,
        )

    def _path_row(
        self,
        parent: ttk.LabelFrame,
        *,
        row: int,
        label: str,
        variable: tk.StringVar,
        browse,
        mnemonic: int,
    ) -> tuple[ttk.Entry, ttk.Button]:
        label_widget = ttk.Label(parent, text=label, underline=mnemonic)
        label_widget.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        entry = ttk.Entry(parent, textvariable=variable)
        entry.grid(row=row, column=1, sticky="ew", pady=4)
        label_widget.configure(takefocus=False)
        button = ttk.Button(
            parent, text="Browse…", command=browse, underline=0
        )
        button.grid(row=row, column=2, padx=(9, 0), pady=4)
        return entry, button

    def _bind_shortcuts(self) -> None:
        self.bind_all("<Alt-c>", lambda _event: self.catalog_entry.focus_set())
        self.bind_all("<Alt-p>", lambda _event: self.previews_entry.focus_set())
        self.bind_all("<Alt-d>", lambda _event: self.output_entry.focus_set())
        self.bind_all("<Alt-s>", lambda _event: self.start_button.invoke())
        self.bind_all("<Alt-x>", lambda _event: self.cancel_button.invoke())

    def _paths_changed(self, *_args: object) -> None:
        self._update_start_enabled()

    def _choose_catalog(self) -> None:
        selected = filedialog.askopenfilename(
            parent=self,
            title="Choose Lightroom catalog",
            initialdir=self._initial_directory(self.catalog_var.get()),
            filetypes=(
                ("Lightroom catalogs", "*.lrcat"),
                ("All files", "*.*"),
            ),
        )
        if selected:
            self.catalog_var.set(selected)

    def _choose_previews(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="Choose Lightroom preview cache (.lrdata)",
            initialdir=self._initial_directory(self.previews_var.get()),
            mustexist=True,
        )
        if selected:
            self.previews_var.set(selected)

    def _choose_output(self) -> None:
        selected = filedialog.askdirectory(
            parent=self,
            title="Choose destination folder",
            initialdir=self._initial_directory(self.output_var.get()),
            mustexist=False,
        )
        if selected:
            self.output_var.set(selected)

    @staticmethod
    def _initial_directory(value: str) -> str:
        if not value.strip():
            return ""
        path = Path(value)
        return str(path if path.is_dir() else path.parent)

    def _config_from_fields(self) -> RecoveryConfig:
        return RecoveryConfig(
            catalog_path=Path(self.catalog_var.get().strip()),
            previews_root=Path(self.previews_var.get().strip()),
            output_parent=Path(self.output_var.get().strip()),
        )

    def _update_start_enabled(self) -> None:
        ready = all(
            variable.get().strip()
            for variable in (
                self.catalog_var,
                self.previews_var,
                self.output_var,
            )
        )
        self._set_enabled(
            self.start_button, ready and self._worker is None
        )

    def _start_recovery(self) -> None:
        if self._worker is not None:
            return
        config = self._config_from_fields()
        self._append_activity("Checking the backup and destination…")
        try:
            preflight = run_preflight(config)
        except Exception as error:
            self._handle_startup_failure("check", error)
            return
        self._active_preflight = preflight
        self._show_preflight(preflight)
        if not preflight.can_start:
            return

        self._reset_run_display(preflight.preview_count)
        self._set_running(True)
        self._output_root = config.output_root
        self._report_path = config.output_root / "recovery-report.html"
        try:
            self._start_worker(config)
        except Exception as error:
            self._handle_startup_failure("start", error)

    def _show_preflight(self, result: PreflightResult) -> None:
        for warning in result.warnings:
            self._append_activity(f"Warning: {warning}")
        if result.blocking_errors:
            self.status_var.set(
                "Cannot start: " + " ".join(result.blocking_errors)
            )
            for error in result.blocking_errors:
                self._append_activity(f"Cannot start: {error}")
            return
        status = (
            f"Ready: {result.catalog_count:,} catalog images and "
            f"{result.preview_count:,} cached previews."
        )
        if result.warnings:
            status += " Review the warnings in activity."
        self.status_var.set(status)

    def _start_worker(self, config: RecoveryConfig) -> None:
        worker = RecoveryWorker(config)
        self._worker = worker
        self._worker_finished_seen = False
        worker.start()
        self._ensure_polling()

    def _handle_startup_failure(
        self, stage: str, error: Exception
    ) -> None:
        self._stop_elapsed_timer()
        worker = self._worker
        if worker is not None:
            worker.cancel()
            worker.join(0)
            if worker.is_running:
                self._ensure_polling()
            else:
                self._worker = None
        self._set_running(self._worker is not None)
        if stage == "check":
            status = (
                "Could not check the backup. Review the details below; "
                "your backup remains unchanged."
            )
            activity = "Could not check the backup"
        else:
            status = (
                "Could not start recovery. Review the details below; "
                "your backup remains unchanged."
            )
            activity = "Could not start recovery"
        self.status_var.set(status)
        self._append_activity(
            f"{activity}: {type(error).__name__}: "
            f"{error or 'unknown error'}"
        )
        self._refresh_open_actions()

    def _ensure_polling(self) -> None:
        if self._poll_after_id is None and not self._destroyed:
            self._poll_after_id = self.after(
                self._POLL_MILLISECONDS, self._poll_worker_events
            )

    def _poll_worker_events(self) -> None:
        self._poll_after_id = None
        worker = self._worker
        if worker is None or self._destroyed:
            return

        for message in worker.drain_messages():
            self._handle_worker_message(message)

        if self._worker is not worker:
            return
        if self._worker_finished_seen and not worker.is_running:
            worker.join(0)
            self._worker = None
            self._worker_finished_seen = False
            self._set_running(False)
            self._refresh_open_actions()
            if not self._terminal_received:
                self.status_var.set(
                    "Recovery stopped before a result was returned."
                )
            if self._close_requested:
                self.after_idle(self._final_destroy)
            return
        self._ensure_polling()

    def _handle_worker_message(self, message: WorkerMessage) -> None:
        if message.kind == "progress":
            if isinstance(message.payload, ProgressSnapshot):
                self._on_progress(message.payload)
        elif message.kind == "completed":
            if isinstance(message.payload, RecoverySummary):
                self._on_completed(message.payload)
        elif message.kind == "failed":
            self._on_failed(str(message.payload))
        elif message.kind == "finished":
            self._worker_finished_seen = True

    def _on_progress(self, snapshot: ProgressSnapshot) -> None:
        self._set_counters(snapshot)
        maximum = int(float(self.progress.cget("maximum")))
        self.progress.configure(
            value=0 if maximum == 0 else min(snapshot.examined, maximum)
        )
        self.progress_help_var.set(
            f"Processed {snapshot.examined:,} of {maximum:,} cached previews."
        )
        self._append_activity(
            f"Processed {snapshot.examined:,} of {maximum:,} previews."
        )

    def _on_completed(self, summary: RecoverySummary) -> None:
        self._terminal_received = True
        self._set_counters(summary)
        maximum = int(float(self.progress.cget("maximum")))
        self.progress.configure(
            value=0 if maximum == 0 else min(summary.examined, maximum)
        )
        self._stop_elapsed_timer()
        if summary.cancelled:
            self.status_var.set(
                "Recovery cancelled safely. A partial report is available."
            )
            self._append_activity(
                "Recovery cancelled safely; completed records and the "
                "partial report were kept."
            )
        else:
            self.status_var.set(
                "Recovery complete. These are cached JPEG previews, "
                "not original photos."
            )
            self._append_activity(
                "Recovery complete. Open the output folder or report "
                "to review the results."
            )
        self._refresh_open_actions()

    def _on_failed(self, message: str) -> None:
        self._terminal_received = True
        self._stop_elapsed_timer()
        self.status_var.set(
            "Recovery failed. See activity for the reason; "
            "your backup remains unchanged."
        )
        self._append_activity(f"Recovery failed: {message}")
        self._refresh_open_actions()

    def _request_cancel(self) -> None:
        worker = self._worker
        if worker is None:
            return
        worker.cancel()
        self._set_enabled(self.cancel_button, False)
        self.status_var.set(
            "Finishing the current preview, then stopping safely…"
        )
        self._append_activity(
            "Cancellation requested. The backup sources remain unchanged."
        )

    def _request_close(self) -> None:
        if self._worker is not None:
            self._close_requested = True
            self._request_cancel()
            self._ensure_polling()
            return
        self._final_destroy()

    def _set_running(self, running: bool) -> None:
        for widget in self._selector_widgets:
            self._set_enabled(widget, not running)
        self._set_enabled(self.cancel_button, running)
        self._update_start_enabled()

    def _reset_run_display(self, preview_count: int) -> None:
        self._terminal_received = False
        self.progress.configure(maximum=preview_count, value=0)
        self.progress_help_var.set(
            "No previews were found in the cache."
            if preview_count == 0
            else f"Ready to process {preview_count:,} cached previews."
        )
        for variable in self.counter_vars.values():
            variable.set("0")
        self._set_enabled(self.open_output_button, False)
        self._set_enabled(self.open_report_button, False)
        self._started_at = time.monotonic()
        self._update_elapsed()

    def _set_counters(
        self, summary: RecoverySummary | ProgressSnapshot
    ) -> None:
        for name in (
            "examined",
            "recovered",
            "unmapped",
            "skipped",
            "failed",
        ):
            self.counter_vars[name].set(f"{getattr(summary, name):,}")

    def _update_elapsed(self) -> None:
        if self._started_at is None or self._destroyed:
            return
        seconds = max(0, int(time.monotonic() - self._started_at))
        self.elapsed_var.set(
            f"Elapsed  {seconds // 3600:02d}:"
            f"{(seconds // 60) % 60:02d}:{seconds % 60:02d}"
        )
        if self._elapsed_after_id is None:
            self._elapsed_after_id = self.after(1000, self._elapsed_tick)

    def _elapsed_tick(self) -> None:
        self._elapsed_after_id = None
        self._update_elapsed()

    def _stop_elapsed_timer(self) -> None:
        callback = self._elapsed_after_id
        self._elapsed_after_id = None
        self._started_at = None
        if callback is not None and not self._destroyed:
            try:
                self.after_cancel(callback)
            except tk.TclError:
                pass

    def _append_activity(self, message: str) -> None:
        self.activity.configure(state="normal")
        self.activity.insert("end", message + "\n")
        self.activity.see("end")
        self.activity.configure(state="disabled")

    def _open_output(self) -> None:
        path = self._output_root
        if path is not None and path.is_dir():
            _open_local_path(path)

    def _open_report(self) -> None:
        path = self._report_path
        if path is not None and path.is_file():
            _open_local_path(path)

    def _open_coffee_link(self) -> None:
        webbrowser.open(COFFEE_URL)

    def _refresh_open_actions(self) -> None:
        self._set_enabled(
            self.open_output_button,
            self._output_root is not None and self._output_root.is_dir(),
        )
        self._set_enabled(
            self.open_report_button,
            self._report_path is not None and self._report_path.is_file(),
        )

    @staticmethod
    def _set_enabled(widget: ttk.Widget, enabled: bool) -> None:
        widget.state(["!disabled"] if enabled else ["disabled"])

    def _cancel_after(self, callback: str | None) -> None:
        if callback is not None:
            try:
                self.after_cancel(callback)
            except tk.TclError:
                pass

    def _final_destroy(self) -> None:
        if self._destroyed:
            return
        worker = self._worker
        if worker is not None and worker.is_running:
            self._close_requested = True
            worker.cancel()
            self._ensure_polling()
            return
        self._cancel_after(self._poll_after_id)
        self._cancel_after(self._elapsed_after_id)
        self._poll_after_id = None
        self._elapsed_after_id = None
        self._destroyed = True
        super().destroy()

    def destroy(self) -> None:
        self._final_destroy()


class SplashScreen(tk.Tk):
    """A brief, borderless launch screen shown before the main window."""

    def __init__(self, *, display_ms: int = 1500) -> None:
        super().__init__()
        self._callback: Callable[[], None] | None = None
        self._dismissed = False
        self._after_id: str | None = None

        self.overrideredirect(True)
        self.configure(background=_GRAPHITE)
        self._center(360, 220)

        ttk.Style(self).configure(
            "Splash.TFrame", background=_GRAPHITE
        )
        ttk.Style(self).configure(
            "SplashTitle.TLabel",
            background=_GRAPHITE,
            foreground=_ACTIVITY_TEXT,
            font=("Georgia", 18, "bold"),
        )
        ttk.Style(self).configure(
            "SplashTagline.TLabel",
            background=_GRAPHITE,
            foreground=_SLATE,
            font=("Segoe UI", 10),
        )

        frame = ttk.Frame(self, style="Splash.TFrame", padding=24)
        frame.grid(row=0, column=0, sticky="nsew")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        ttk.Label(
            frame,
            text="Lightroom Preview Recovery",
            style="SplashTitle.TLabel",
            anchor="center",
            justify="center",
        ).grid(row=0, column=0, sticky="ew")
        ttk.Label(
            frame,
            text="Recovering cached previews from your backup…",
            style="SplashTagline.TLabel",
            anchor="center",
            justify="center",
        ).grid(row=1, column=0, sticky="ew", pady=(10, 0))

        self.bind("<Button-1>", lambda _event: self._dismiss())
        self._after_id = self.after(display_ms, self._dismiss)

    def _center(self, width: int, height: int) -> None:
        self.update_idletasks()
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = max(0, (screen_width - width) // 2)
        y = max(0, (screen_height - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

    def on_dismiss(self, callback: Callable[[], None]) -> None:
        """Register the callback to run once, when the splash closes."""
        self._callback = callback

    def _dismiss(self) -> None:
        if self._dismissed:
            return
        self._dismissed = True
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        callback = self._callback
        self.destroy()
        if callback is not None:
            callback()
