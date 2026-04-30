from __future__ import annotations

import threading
import tkinter as tk
from queue import Empty, Queue
from tkinter import ttk
from typing import Callable, Dict, Optional, Tuple

from utils import get_status_color


class TranslatorUI:
    def __init__(
        self,
        language_names: list[str],
        source_language_options: list[str],
        engine_options: list[str],
        on_start: Callable[[], None],
        on_stop: Callable[[], None],
        on_close: Callable[[], None],
    ) -> None:
        self.on_start = on_start
        self.on_stop = on_stop
        self.on_close = on_close

        self.root = tk.Tk()
        self.root.title("AI Real-Time Voice Translator")
        self.root.geometry("1240x820")
        self.root.minsize(1080, 700)
        self.root.configure(bg="#0b1220")
        self.root.protocol("WM_DELETE_WINDOW", self._handle_close)
        self.root.bind("<Control-Return>", self._on_start_shortcut)
        self.root.bind("<Escape>", self._on_stop_shortcut)

        self._queue: Optional[Queue] = None
        self._option_lock = threading.Lock()

        self.source_language_var = tk.StringVar(value=source_language_options[0])
        self.target_language_var = tk.StringVar(value=language_names[0])
        self.engine_var = tk.StringVar(value=engine_options[0])

        self._source_language = self.source_language_var.get()
        self._target_language = self.target_language_var.get()
        self._engine = self.engine_var.get()

        self.source_language_var.trace_add("write", self._refresh_option_snapshot)
        self.target_language_var.trace_add("write", self._refresh_option_snapshot)
        self.engine_var.trace_add("write", self._refresh_option_snapshot)

        self._build_styles()
        self._build_layout(language_names, source_language_options, engine_options)

    def _on_start_shortcut(self, _event: object) -> str:
        self._on_start_clicked()
        return "break"

    def _on_stop_shortcut(self, _event: object) -> str:
        self._on_stop_clicked()
        return "break"

    def _on_start_clicked(self) -> None:
        # Immediate visual feedback for demos; worker thread will emit authoritative status.
        # Lock controls immediately to prevent accidental double-starts before worker emits state.
        try:
            self._set_running(True)
            self._clear_history()
        except Exception:
            # Keyboard shortcuts could fire before full layout is constructed.
            pass
        self._clear_text_widget(getattr(self, "_original_text_widget", None))
        self._clear_text_widget(getattr(self, "_translated_text_widget", None))
        if hasattr(self, "detected_label"):
            self.detected_label.config(text="Detected: -")
        if hasattr(self, "speaking_label"):
            self.speaking_label.config(text="Now speaking: -")
        self.on_start()

    def _on_stop_clicked(self) -> None:
        # Quick feedback; actual status will be updated from worker thread.
        try:
            self._set_status("Stopping...", "processing")
        except Exception:
            pass
        # Keep controls locked while stopping to avoid accidental re-starts mid-shutdown.
        try:
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="disabled")
            self.source_combo.configure(state="disabled")
            self.target_combo.configure(state="disabled")
            self.engine_combo.configure(state="disabled")
        except Exception:
            pass
        self.on_stop()

    def attach_queue(self, queue_obj: Queue) -> None:
        self._queue = queue_obj
        self.root.after(80, self._drain_queue)

    def run(self) -> None:
        self.root.mainloop()

    def get_runtime_options(self) -> Tuple[str, str, str]:
        with self._option_lock:
            return self._source_language, self._target_language, self._engine

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")

        style.configure("Card.TFrame", background="#111b2f")
        style.configure("Panel.TLabelframe", background="#111b2f", foreground="#e5ecff")
        style.configure("Panel.TLabelframe.Label", background="#111b2f", foreground="#e5ecff")
        style.configure(
            "Title.TLabel",
            background="#0b1220",
            foreground="#ffffff",
            font=("Segoe UI", 21, "bold"),
        )
        style.configure(
            "SubTitle.TLabel",
            background="#0b1220",
            foreground="#9bb0d3",
            font=("Segoe UI", 10),
        )
        style.configure(
            "Field.TLabel",
            background="#111b2f",
            foreground="#dbe7ff",
            font=("Segoe UI", 10, "bold"),
        )
        style.configure(
            "Action.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 8),
            foreground="#ffffff",
            background="#1d4ed8",
        )
        style.map("Action.TButton", background=[("active", "#2563eb"), ("disabled", "#334155")])
        style.configure(
            "Stop.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(12, 8),
            foreground="#ffffff",
            background="#e11d48",
        )
        style.map("Stop.TButton", background=[("active", "#f43f5e"), ("disabled", "#334155")])

        style.configure(
            "Ghost.TButton",
            font=("Segoe UI", 10, "bold"),
            padding=(10, 7),
            foreground="#e2e8f0",
            background="#334155",
        )
        style.map(
            "Ghost.TButton",
            background=[("active", "#475569"), ("disabled", "#334155")],
        )

        style.configure(
            "Modern.TCombobox",
            fieldbackground="#0f172a",
            foreground="#e2e8f0",
            background="#0f172a",
            arrowsize=14,
            padding=6,
        )
        # Ensure combobox text remains visible on Windows in readonly mode.
        style.map(
            "Modern.TCombobox",
            fieldbackground=[("readonly", "#0f172a"), ("disabled", "#1e293b")],
            foreground=[("readonly", "#e2e8f0"), ("disabled", "#94a3b8")],
            selectbackground=[("readonly", "#1d4ed8")],
            selectforeground=[("readonly", "#ffffff")],
        )

        # Dropdown list colors for better contrast across platforms/themes.
        self.root.option_add("*TCombobox*Listbox.background", "#0f172a")
        self.root.option_add("*TCombobox*Listbox.foreground", "#e2e8f0")
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#1d4ed8")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")

        style.configure(
            "StatusProgressListening.Horizontal.TProgressbar",
            troughcolor="#0f172a",
            background="#1db954",
            thickness=8,
        )
        style.configure(
            "StatusProgressProcessing.Horizontal.TProgressbar",
            troughcolor="#0f172a",
            background="#2e86de",
            thickness=8,
        )
        style.configure(
            "StatusProgressError.Horizontal.TProgressbar",
            troughcolor="#0f172a",
            background="#e74c3c",
            thickness=8,
        )

    def _build_layout(
        self, language_names: list[str], source_language_options: list[str], engine_options: list[str]
    ) -> None:
        container = ttk.Frame(self.root, style="Card.TFrame", padding=18)
        container.pack(fill="both", expand=True, padx=18, pady=18)
        container.columnconfigure(0, weight=1)
        container.rowconfigure(2, weight=1)
        container.rowconfigure(3, weight=1)

        heading_frame = ttk.Frame(container, style="Card.TFrame")
        heading_frame.grid(row=0, column=0, sticky="ew")
        heading_frame.columnconfigure(0, weight=1)

        ttk.Label(heading_frame, text="AI Real-Time Voice Translator", style="Title.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(
            heading_frame,
            text="Speak naturally for up to ~20 seconds. The app detects, translates, and speaks instantly. (Ctrl+Enter to start, Esc to stop)",
            style="SubTitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        status_frame = ttk.Frame(heading_frame, style="Card.TFrame")
        status_frame.grid(row=0, column=1, rowspan=2, sticky="e")
        self.status_dot = tk.Label(
            status_frame,
            text="  ",
            bg="#95a5a6",
            width=2,
            relief="flat",
        )
        self.status_dot.grid(row=0, column=0, padx=(0, 8))
        self.status_label = tk.Label(
            status_frame,
            text="Status: Idle",
            bg="#0b1220",
            fg="#dbeafe",
            font=("Segoe UI", 10, "bold"),
        )
        self.status_label.grid(row=0, column=1, sticky="w")
        self.detected_label = tk.Label(
            status_frame,
            text="Detected: -",
            bg="#0b1220",
            fg="#93c5fd",
            font=("Segoe UI", 9),
        )
        self.detected_label.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.progress = ttk.Progressbar(
            status_frame,
            mode="indeterminate",
            length=180,
            style="StatusProgressListening.Horizontal.TProgressbar",
        )
        self.progress.grid(row=2, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.progress.grid_remove()

        self.speaking_label = tk.Label(
            status_frame,
            text="Now speaking: -",
            bg="#0b1220",
            fg="#e5e7eb",
            font=("Segoe UI", 9),
            anchor="w",
        )
        self.speaking_label.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))

        control_frame = ttk.LabelFrame(
            container, text="Controls", style="Panel.TLabelframe", padding=(14, 12)
        )
        control_frame.grid(row=1, column=0, sticky="ew", pady=(14, 12))
        for index in range(6):
            control_frame.columnconfigure(index, weight=1)

        ttk.Label(control_frame, text="Source Language", style="Field.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        self.source_combo = ttk.Combobox(
            control_frame,
            textvariable=self.source_language_var,
            values=source_language_options,
            state="readonly",
            style="Modern.TCombobox",
        )
        self.source_combo.grid(row=1, column=0, sticky="ew", pady=(6, 0), padx=(0, 8))

        ttk.Label(control_frame, text="Target Language", style="Field.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        self.target_combo = ttk.Combobox(
            control_frame,
            textvariable=self.target_language_var,
            values=language_names,
            state="readonly",
            style="Modern.TCombobox",
        )
        self.target_combo.grid(row=1, column=1, sticky="ew", pady=(6, 0), padx=(0, 8))

        ttk.Label(control_frame, text="Translation Engine", style="Field.TLabel").grid(
            row=0, column=2, sticky="w"
        )
        self.engine_combo = ttk.Combobox(
            control_frame,
            textvariable=self.engine_var,
            values=engine_options,
            state="readonly",
            style="Modern.TCombobox",
        )
        self.engine_combo.grid(row=1, column=2, sticky="ew", pady=(6, 0), padx=(0, 8))

        self.start_button = ttk.Button(
            control_frame,
            text="Start Listening",
            style="Action.TButton",
            command=self._on_start_clicked,
        )
        self.start_button.grid(row=1, column=4, sticky="ew", padx=(8, 8))

        self.stop_button = ttk.Button(
            control_frame,
            text="Stop",
            style="Stop.TButton",
            command=self._on_stop_clicked,
            state="disabled",
        )
        self.stop_button.grid(row=1, column=5, sticky="ew")

        text_frame = ttk.Frame(container, style="Card.TFrame")
        text_frame.grid(row=2, column=0, sticky="nsew", pady=(0, 12))
        text_frame.columnconfigure(0, weight=1)
        text_frame.columnconfigure(1, weight=1)
        text_frame.rowconfigure(0, weight=1)

        self.original_text = self._create_text_panel(text_frame, "Original Speech")
        self.original_text.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.translated_text = self._create_text_panel(text_frame, "Translated Speech")
        self.translated_text.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        history_panel = ttk.LabelFrame(
            container, text="Translation History", style="Panel.TLabelframe", padding=10
        )
        history_panel.grid(row=3, column=0, sticky="nsew")
        history_panel.columnconfigure(0, weight=1)
        history_panel.rowconfigure(1, weight=1)

        history_toolbar = ttk.Frame(history_panel, style="Card.TFrame")
        history_toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        history_toolbar.columnconfigure(0, weight=1)
        ttk.Label(
            history_toolbar,
            text="Latest translations appear here.",
            style="SubTitle.TLabel",
        ).grid(row=0, column=0, sticky="w")
        ttk.Button(
            history_toolbar,
            text="Clear History",
            style="Ghost.TButton",
            command=self._clear_history,
        ).grid(row=0, column=1, sticky="e", padx=(12, 0))

        self.history_text = tk.Text(
            history_panel,
            wrap="word",
            font=("Segoe UI", 10),
            background="#0f172a",
            foreground="#dbeafe",
            insertbackground="#dbeafe",
            height=10,
            relief="flat",
            padx=10,
            pady=10,
        )
        history_scroll = ttk.Scrollbar(history_panel, orient="vertical", command=self.history_text.yview)
        self.history_text.configure(yscrollcommand=history_scroll.set)
        self.history_text.grid(row=1, column=0, sticky="nsew")
        history_scroll.grid(row=1, column=1, sticky="ns")
        self.history_text.configure(state="disabled")

    def _create_text_panel(self, parent: ttk.Frame, title: str) -> ttk.Frame:
        panel = ttk.LabelFrame(parent, text=title, style="Panel.TLabelframe", padding=10)
        panel.columnconfigure(0, weight=1)
        panel.rowconfigure(1, weight=1)

        toolbar = ttk.Frame(panel, style="Card.TFrame")
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        toolbar.columnconfigure(0, weight=1)

        text_widget = tk.Text(
            panel,
            wrap="word",
            font=("Segoe UI", 11),
            background="#0f172a",
            foreground="#e2e8f0",
            insertbackground="#e2e8f0",
            relief="flat",
            padx=10,
            pady=10,
        )

        ttk.Button(
            toolbar,
            text="Copy",
            style="Ghost.TButton",
            command=lambda: self._copy_text_widget(text_widget),
        ).grid(row=0, column=1, sticky="e")
        ttk.Button(
            toolbar,
            text="Clear",
            style="Ghost.TButton",
            command=lambda: self._clear_text_widget(text_widget),
        ).grid(row=0, column=2, sticky="e", padx=(8, 0))

        text_scroll = ttk.Scrollbar(panel, orient="vertical", command=text_widget.yview)
        text_widget.configure(yscrollcommand=text_scroll.set)
        text_widget.grid(row=1, column=0, sticky="nsew")
        text_scroll.grid(row=1, column=1, sticky="ns")
        text_widget.configure(state="disabled")

        if title == "Original Speech":
            self._original_text_widget = text_widget
        else:
            self._translated_text_widget = text_widget

        return panel

    def _refresh_option_snapshot(self, *_args: object) -> None:
        with self._option_lock:
            self._source_language = self.source_language_var.get()
            self._target_language = self.target_language_var.get()
            self._engine = self.engine_var.get()

    def _drain_queue(self) -> None:
        if self._queue is not None:
            while True:
                try:
                    event = self._queue.get_nowait()
                except Empty:
                    break
                # All widget updates happen on tkinter main thread via queued events.
                self._handle_event(event)

        try:
            self.root.after(80, self._drain_queue)
        except tk.TclError:
            return

    def _handle_event(self, event: Dict[str, object]) -> None:
        event_type = event.get("type")

        if event_type == "status":
            self._set_status(str(event.get("text", "Status update")), str(event.get("state", "idle")))
            return

        if event_type == "controls":
            self._set_running(bool(event.get("running", False)))
            return

        if event_type == "detected":
            detected = str(event.get("language", "-"))
            self.detected_label.config(text=f"Detected: {detected}")
            return

        if event_type == "original":
            self._replace_text(self._original_text_widget, str(event.get("text", "")))
            return

        if event_type == "translated":
            translated_text = str(event.get("text", ""))
            self._replace_text(self._translated_text_widget, translated_text)
            if hasattr(self, "speaking_label"):
                display_text = translated_text.strip()
                if len(display_text) > 70:
                    display_text = display_text[:67] + "..."
                self.speaking_label.config(text=f"Now speaking: {display_text or '-'}")
            return

        if event_type == "history":
            self._append_history(str(event.get("entry", "")))
            return

        if event_type == "error":
            message = str(event.get("message", "An unexpected error occurred."))
            self._set_status(message, "error")
            self._append_history(f"[ERROR] {message}")

    def _set_running(self, running: bool) -> None:
        if running:
            self.start_button.configure(state="disabled")
            self.stop_button.configure(state="normal")
            self.source_combo.configure(state="disabled")
            self.target_combo.configure(state="disabled")
            self.engine_combo.configure(state="disabled")
        else:
            self.start_button.configure(state="normal")
            self.stop_button.configure(state="disabled")
            self.source_combo.configure(state="readonly")
            self.target_combo.configure(state="readonly")
            self.engine_combo.configure(state="readonly")

    def _set_status(self, text: str, state: str) -> None:
        state_norm = state.lower().strip()
        color, _ = get_status_color(state)
        self.status_dot.configure(bg=color)
        self.status_label.configure(text=f"Status: {text}")
        if hasattr(self, "progress"):
            if state_norm == "listening":
                self.progress.configure(style="StatusProgressListening.Horizontal.TProgressbar")
            elif state_norm == "processing":
                self.progress.configure(style="StatusProgressProcessing.Horizontal.TProgressbar")
            elif state_norm == "error":
                self.progress.configure(style="StatusProgressError.Horizontal.TProgressbar")

            if state_norm in ("listening", "processing"):
                self.progress.grid()
                self.progress.start(10)
            else:
                self.progress.stop()
                self.progress.grid_remove()

        if hasattr(self, "speaking_label"):
            if state_norm in ("idle", "error"):
                self.speaking_label.config(text="Now speaking: -")

    @staticmethod
    def _replace_text(widget: tk.Text, text: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.insert("1.0", text)
        widget.configure(state="disabled")

    def _append_history(self, entry: str) -> None:
        if not entry.strip():
            return
        self.history_text.configure(state="normal")
        self.history_text.insert("end", f"{entry}\n\n")
        self.history_text.see("end")
        # Keep history bounded so the UI remains snappy in demos.
        max_history_lines = 120
        try:
            end_line = int(self.history_text.index("end-1c").split(".")[0])
        except Exception:
            end_line = 0
        if end_line > max_history_lines:
            self.history_text.delete("1.0", f"end-{max_history_lines}l")
        self.history_text.configure(state="disabled")

    def _clear_history(self) -> None:
        self.history_text.configure(state="normal")
        self.history_text.delete("1.0", "end")
        self.history_text.configure(state="disabled")

    @staticmethod
    def _copy_text_widget(widget: Optional[tk.Text]) -> None:
        if widget is None:
            return
        prev_state = widget.cget("state")
        # Ensure clipboard copy works even when the widget is disabled.
        widget.configure(state="normal")
        text = widget.get("1.0", "end-1c").strip()
        widget.configure(state=prev_state)
        if not text:
            return
        widget.clipboard_clear()
        widget.clipboard_append(text)

    @staticmethod
    def _clear_text_widget(widget: Optional[tk.Text]) -> None:
        if widget is None:
            return
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        widget.configure(state="disabled")

    def _handle_close(self) -> None:
        self.on_close()
