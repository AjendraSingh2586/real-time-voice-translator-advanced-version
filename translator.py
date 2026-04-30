from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Dict, List, Tuple

from googletrans import Translator as GoogleTranslator

from utils import (
    AUTO_DETECT_LABEL,
    GOOGLE_ENGINE_LABEL,
    SARVAM_ENGINE_LABEL,
    get_google_language_code,
    get_language_name_from_code,
    get_sarvam_code,
)


class TranslationError(Exception):
    pass


@dataclass
class TranslationResult:
    original_text: str
    translated_text: str
    source_language_code: str
    source_language_name: str
    target_language_code: str
    target_language_name: str
    engine_used: str


class TranslationService:
    def __init__(self) -> None:
        self.sarvam_url = os.getenv("SARVAM_TRANSLATE_URL", "https://api.sarvam.ai/translate")
        self.sarvam_api_key = os.getenv("SARVAM_API_KEY", "").strip()
        self.sarvam_timeout = float(os.getenv("SARVAM_TIMEOUT_SECONDS", "20"))

    # ✅ FIXED (removed asyncio)
    def detect_language(self, text: str) -> Tuple[str, str]:
        if not text.strip():
            return "unknown", "Unknown"

        try:
            google = GoogleTranslator()
            detected = google.detect(text)   # ❌ no asyncio.run
            code = (detected.lang or "unknown").lower()
            return code, get_language_name_from_code(code)
        except Exception:
            return "unknown", "Unknown"

    def translate_text(
        self,
        text: str,
        target_language_name: str,
        source_language_name: str = AUTO_DETECT_LABEL,
        preferred_engine: str = GOOGLE_ENGINE_LABEL,
    ) -> TranslationResult:
        cleaned_text = text.strip()
        if not cleaned_text:
            raise TranslationError("No text received for translation.")

        target_code = get_google_language_code(target_language_name)
        detected_code, detected_name = self.detect_language(cleaned_text)

        if source_language_name == AUTO_DETECT_LABEL:
            source_code = detected_code if detected_code != "unknown" else "auto"
            source_name = detected_name
        else:
            source_code = get_google_language_code(source_language_name)
            source_name = source_language_name

        if source_code == target_code:
            return TranslationResult(
                original_text=cleaned_text,
                translated_text=cleaned_text,
                source_language_code=source_code,
                source_language_name=source_name,
                target_language_code=target_code,
                target_language_name=target_language_name,
                engine_used="No translation needed",
            )

        engines = self._build_engine_try_order(preferred_engine)
        errors: List[str] = []

        for engine in engines:
            try:
                translated = self._translate_with_engine(
                    engine=engine,
                    text=cleaned_text,
                    source_code=source_code,
                    target_code=target_code,
                )
                if translated.strip():
                    return TranslationResult(
                        original_text=cleaned_text,
                        translated_text=translated.strip(),
                        source_language_code=source_code,
                        source_language_name=source_name,
                        target_language_code=target_code,
                        target_language_name=target_language_name,
                        engine_used=engine,
                    )
            except TranslationError as exc:
                errors.append(f"{engine}: {exc}")

        error_text = " | ".join(errors) if errors else "Unknown translation failure."
        raise TranslationError(error_text)

    # ✅ FIXED: avoid Sarvam if no API key
    def _build_engine_try_order(self, preferred_engine: str) -> List[str]:
        engine = preferred_engine.strip().lower()

        if not self.sarvam_api_key:
            return [GOOGLE_ENGINE_LABEL]

        if engine == SARVAM_ENGINE_LABEL.lower():
            return [SARVAM_ENGINE_LABEL, GOOGLE_ENGINE_LABEL]

        return [GOOGLE_ENGINE_LABEL, SARVAM_ENGINE_LABEL]

    def _translate_with_engine(
        self, engine: str, text: str, source_code: str, target_code: str
    ) -> str:
        if engine == GOOGLE_ENGINE_LABEL:
            return self._translate_google(text, source_code, target_code)
        if engine == SARVAM_ENGINE_LABEL:
            return self._translate_sarvam(text, source_code, target_code)
        raise TranslationError(f"Unknown engine: {engine}")

    # ✅ FIXED (removed asyncio)
    def _translate_google(self, text: str, source_code: str, target_code: str) -> str:
        try:
            source = source_code if source_code != "unknown" else "auto"
            google = GoogleTranslator()
            translated = google.translate(text, src=source, dest=target_code)  # ❌ no asyncio
            return translated.text
        except Exception as exc:
            raise TranslationError(f"Google translation failed: {exc}") from exc

    def _translate_sarvam(self, text: str, source_code: str, target_code: str) -> str:
        if not self.sarvam_api_key:
            raise TranslationError("Sarvam API key not configured.")

        sarvam_source = self._resolve_sarvam_source_code(source_code)
        sarvam_target = get_sarvam_code(target_code)
        if not sarvam_target:
            raise TranslationError("Target language is not supported by Sarvam.")

        payload = {
            "input": text,
            "source_language_code": sarvam_source,
            "target_language_code": sarvam_target,
        }

        request_data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "api-subscription-key": self.sarvam_api_key,
        }

        request = urllib.request.Request(
            self.sarvam_url, data=request_data, headers=headers, method="POST"
        )

        try:
            with urllib.request.urlopen(request, timeout=self.sarvam_timeout) as response:
                body = response.read().decode("utf-8")
                parsed = json.loads(body)
        except Exception as exc:
            raise TranslationError(f"Sarvam failed: {exc}") from exc

        return parsed.get("translated_text", "")