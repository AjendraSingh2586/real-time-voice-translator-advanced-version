from __future__ import annotations

import os
import tempfile
import threading
import time
from typing import Optional

import pygame
from gtts import gTTS


class SpeechOutputError(Exception):
    pass


class SpeechOutput:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._current_temp_file: Optional[str] = None
        self._cleanup_thread: Optional[threading.Thread] = None

        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
        except pygame.error as exc:
            raise SpeechOutputError(f"Failed to initialize audio output: {exc}") from exc

    def speak(self, text: str, tts_language: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            raise SpeechOutputError("Cannot speak empty text.")

        temp_path = self._create_tts_file(cleaned, tts_language)

        with self._lock:
            self._stop_locked()
            try:
                pygame.mixer.music.load(temp_path)
                pygame.mixer.music.play()
            except pygame.error as exc:
                self._safe_remove(temp_path)
                raise SpeechOutputError(f"Failed to play audio: {exc}") from exc

            self._current_temp_file = temp_path
            self._cleanup_thread = threading.Thread(
                # Playback cleanup runs in background so UI/audio thread stays responsive.
                target=self._cleanup_when_playback_finishes, daemon=True
            )
            self._cleanup_thread.start()

    def stop(self) -> None:
        with self._lock:
            self._stop_locked()

    def shutdown(self) -> None:
        with self._lock:
            self._stop_locked()
            try:
                pygame.mixer.quit()
            except pygame.error:
                pass

    def _create_tts_file(self, text: str, language_code: str) -> str:
        file_handle = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
        file_path = file_handle.name
        file_handle.close()

        try:
            gTTS(text=text, lang=language_code, slow=False).save(file_path)
            return file_path
        except Exception as exc:
            self._safe_remove(file_path)
            raise SpeechOutputError(f"Text-to-speech failed: {exc}") from exc

    def _cleanup_when_playback_finishes(self) -> None:
        while True:
            with self._lock:
                playing = pygame.mixer.music.get_busy()
                current_file = self._current_temp_file
            if not playing:
                break
            time.sleep(0.1)

        with self._lock:
            try:
                pygame.mixer.music.unload()
            except pygame.error:
                pass
            if current_file and current_file == self._current_temp_file:
                self._safe_remove(current_file)
                self._current_temp_file = None

    def _stop_locked(self) -> None:
        try:
            if pygame.mixer.music.get_busy():
                pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except pygame.error:
            pass

        if self._current_temp_file:
            self._safe_remove(self._current_temp_file)
            self._current_temp_file = None

    @staticmethod
    def _safe_remove(path: str) -> None:
        # Windows can briefly hold file locks after pygame unload/stop.
        for _ in range(5):
            try:
                os.remove(path)
                return
            except OSError:
                time.sleep(0.05)
