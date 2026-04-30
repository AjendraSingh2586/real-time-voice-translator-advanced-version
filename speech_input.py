from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Optional

import speech_recognition as sr


class SpeechInputError(Exception):
    pass


class MicrophoneNotFoundError(SpeechInputError):
    pass


class SpeechTimeoutError(SpeechInputError):
    pass


class SpeechNotRecognizedError(SpeechInputError):
    pass


@dataclass
class SpeechCaptureResult:
    text: str
    locale_used: Optional[str]


class SpeechInput:
    def __init__(
        self,
        sample_rate: int = 16000,
        max_phrase_seconds: int = 20,
        ambient_calibration_seconds: float = 0.8,
    ) -> None:
        self.sample_rate = sample_rate
        self.max_phrase_seconds = max_phrase_seconds
        self.ambient_calibration_seconds = ambient_calibration_seconds

        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.0
        self.recognizer.non_speaking_duration = 0.7
        self.recognizer.dynamic_energy_threshold = True

        self._calibrated = False

    def _get_microphone(self) -> sr.Microphone:
        try:
            return sr.Microphone(sample_rate=self.sample_rate)
        except OSError as exc:
            raise MicrophoneNotFoundError(
                "Microphone not found or unavailable. Connect a microphone and try again."
            ) from exc

    def capture_sentence(
        self,
        preferred_locale: Optional[str] = None,
        auto_detect: bool = True,
        candidate_locales: Optional[Iterable[str]] = None,
        wait_timeout_seconds: int = 5,
    ) -> SpeechCaptureResult:
        with self._get_microphone() as source:
            if not self._calibrated:
                self.recognizer.adjust_for_ambient_noise(
                    source, duration=self.ambient_calibration_seconds
                )
                self._calibrated = True

            try:
                # phrase_time_limit allows capturing longer sentences (~15-20 seconds) in one go.
                audio_data = self.recognizer.listen(
                    source,
                    timeout=wait_timeout_seconds,
                    phrase_time_limit=self.max_phrase_seconds,
                )
            except sr.WaitTimeoutError as exc:
                raise SpeechTimeoutError("No speech detected. Please try speaking again.") from exc

        locales_to_try = self._build_locale_try_order(
            preferred_locale=preferred_locale,
            auto_detect=auto_detect,
            candidate_locales=candidate_locales,
        )

        request_errors: List[str] = []
        for locale in locales_to_try:
            try:
                # Try multiple locales when auto-detect is enabled to reduce missed recognition.
                text = self.recognizer.recognize_google(audio_data, language=locale)
                cleaned = text.strip()
                if cleaned:
                    return SpeechCaptureResult(text=cleaned, locale_used=locale)
            except sr.UnknownValueError:
                continue
            except sr.RequestError as exc:
                request_errors.append(str(exc))

        if request_errors:
            raise SpeechInputError(
                "Speech recognition service error. Check your internet connection and retry."
            )

        raise SpeechNotRecognizedError(
            "Speech could not be recognized clearly. Please speak a little louder and retry."
        )

    @staticmethod
    def _build_locale_try_order(
        preferred_locale: Optional[str],
        auto_detect: bool,
        candidate_locales: Optional[Iterable[str]],
    ) -> List[str]:
        ordered: List[str] = []
        if preferred_locale:
            ordered.append(preferred_locale)

        if auto_detect:
            auto_candidates = list(candidate_locales or [])
            for locale in auto_candidates:
                if locale not in ordered:
                    ordered.append(locale)

            if "en-US" not in ordered:
                ordered.append("en-US")
        elif not ordered:
            ordered.append("en-US")

        return ordered
