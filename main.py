from __future__ import annotations

import threading
import time
from queue import Queue
from typing import Optional

from speech_input import (
    MicrophoneNotFoundError,
    SpeechCaptureResult,
    SpeechInput,
    SpeechInputError,
    SpeechNotRecognizedError,
    SpeechTimeoutError,
)
from speech_output import SpeechOutput, SpeechOutputError
from translator import TranslationError, TranslationResult, TranslationService
from ui import TranslatorUI
from utils import (
    AUTO_DETECT_LABEL,
    get_all_speech_locales,
    get_language_name_from_code,
    get_language_names,
    get_source_language_options,
    get_speech_locale,
    get_translation_engine_options,
    timestamp_now,
)


class AppController:
    def __init__(self) -> None:
        self.ui_queue: Queue = Queue()
        self.stop_event = threading.Event()
        self._state_lock = threading.Lock()
        self._running = False
        self.worker_thread: Optional[threading.Thread] = None

        self.speech_input = SpeechInput(max_phrase_seconds=20)
        self.translator = TranslationService()
        self.speech_output: Optional[SpeechOutput] = None
        self._pending_audio_error: Optional[str] = None

        try:
            self.speech_output = SpeechOutput()
        except SpeechOutputError as exc:
            self._pending_audio_error = str(exc)

        self.ui = TranslatorUI(
            language_names=get_language_names(),
            source_language_options=get_source_language_options(),
            engine_options=get_translation_engine_options(),
            on_start=self.start,
            on_stop=self.stop,
            on_close=self.shutdown,
        )
        self.ui.attach_queue(self.ui_queue)

        self._emit_status("Idle", "idle")
        if self._pending_audio_error:
            self._emit_error(f"Audio output unavailable: {self._pending_audio_error}")

    def run(self) -> None:
        self.ui.run()

    def start(self) -> None:
        with self._state_lock:
            if self._running:
                return
            self._running = True
            self.stop_event.clear()
            self.worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
            self.worker_thread.start()

        self._emit_control_state(running=True)
        self._emit_status("Listening...", "listening")

    def stop(self) -> None:
        with self._state_lock:
            if not self._running:
                return
        self.stop_event.set()
        if self.speech_output is not None:
            self.speech_output.stop()
        self._emit_status("Stopping...", "processing")

    def shutdown(self) -> None:
        self.stop_event.set()
        if self.speech_output is not None:
            self.speech_output.shutdown()

        thread = self.worker_thread
        if thread and thread.is_alive():
            thread.join(timeout=2)

        self.ui.root.destroy()

    def _worker_loop(self) -> None:
        locales = get_all_speech_locales()
        while not self.stop_event.is_set():
            # Read options from UI snapshot so worker thread never touches tkinter widgets directly.
            source_language, target_language, engine = self.ui.get_runtime_options()
            capture_result = self._listen_once(source_language, locales)
            if capture_result is None:
                continue
            if self.stop_event.is_set():
                break

            original_text = capture_result.text.strip()
            if not original_text:
                continue

            self._emit_event({"type": "original", "text": original_text})
            self._emit_status("Processing...", "processing")

            try:
                translation = self.translator.translate_text(
                    text=original_text,
                    target_language_name=target_language,
                    source_language_name=source_language,
                    preferred_engine=engine,
                )
            except TranslationError as exc:
                self._emit_error(f"Translation failed: {exc}")
                continue

            detected_name = self._resolve_detected_language_name(
                result=translation, capture_result=capture_result
            )
            self._emit_event({"type": "detected", "language": detected_name})
            self._emit_event({"type": "translated", "text": translation.translated_text})
            self._emit_event({"type": "history", "entry": self._build_history_entry(translation)})

            if self.speech_output is not None:
                try:
                    # New translation interrupts any previous playback for real-time behavior.
                    self.speech_output.speak(
                        text=translation.translated_text,
                        tts_language=translation.target_language_code,
                    )
                except SpeechOutputError as exc:
                    self._emit_error(f"Text-to-speech failed: {exc}")

        with self._state_lock:
            self._running = False
        self._emit_control_state(running=False)
        self._emit_status("Idle", "idle")

    def _listen_once(
        self, source_language: str, all_locales: list[str]
    ) -> Optional[SpeechCaptureResult]:
        preferred_locale = None
        auto_detect = source_language == AUTO_DETECT_LABEL
        if not auto_detect:
            try:
                preferred_locale = get_speech_locale(source_language)
            except KeyError:
                self._emit_error(f"Unsupported source language for speech recognition: {source_language}")
                return None

        self._emit_status("Listening...", "listening")
        try:
            return self.speech_input.capture_sentence(
                preferred_locale=preferred_locale,
                auto_detect=auto_detect,
                candidate_locales=all_locales,
                wait_timeout_seconds=5,
            )
        except SpeechTimeoutError:
            return None
        except MicrophoneNotFoundError as exc:
            self._emit_error(str(exc))
            time.sleep(0.6)
            return None
        except SpeechNotRecognizedError as exc:
            self._emit_error(str(exc))
            time.sleep(0.3)
            return None
        except SpeechInputError as exc:
            self._emit_error(str(exc))
            time.sleep(0.5)
            return None

    @staticmethod
    def _resolve_detected_language_name(
        result: TranslationResult, capture_result: SpeechCaptureResult
    ) -> str:
        if result.source_language_name and result.source_language_name.lower() != "unknown":
            return result.source_language_name

        if capture_result.locale_used:
            locale_prefix = capture_result.locale_used.split("-")[0].lower()
            return get_language_name_from_code(locale_prefix)

        return "Unknown"

    @staticmethod
    def _build_history_entry(result: TranslationResult) -> str:
        return (
            f"[{timestamp_now()}] Engine: {result.engine_used} | "
            f"{result.source_language_name} -> {result.target_language_name}\n"
            f"Original: {result.original_text}\n"
            f"Translated: {result.translated_text}"
        )

    def _emit_status(self, text: str, state: str) -> None:
        self._emit_event({"type": "status", "text": text, "state": state})

    def _emit_error(self, message: str) -> None:
        self._emit_event({"type": "error", "message": message})

    def _emit_control_state(self, running: bool) -> None:
        self._emit_event({"type": "controls", "running": running})

    def _emit_event(self, event: dict) -> None:
        self.ui_queue.put(event)


def main() -> None:
    app = AppController()
    app.run()


if __name__ == "__main__":
    main()
