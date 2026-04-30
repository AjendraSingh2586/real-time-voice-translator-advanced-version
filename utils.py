from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Tuple


# Display name -> googletrans / gTTS language code
LANGUAGE_TO_CODE: Dict[str, str] = {
    "Spanish": "es",
    "Hindi": "hi",
    "English": "en",
    "French": "fr",
    "German": "de",
    "Arabic": "ar",
    "Russian": "ru",
    "Mandarin (Chinese)": "zh-cn",
    "Portuguese": "pt",
    "Italian": "it",
    "Japanese": "ja",
    "Korean": "ko",
    "Bengali": "bn",
    "Marathi": "mr",
    "Telugu": "te",
    "Tamil": "ta",
    "Gujarati": "gu",
    "Urdu": "ur",
    "Kannada": "kn",
    "Odia": "or",
    "Malayalam": "ml",
    "Nepali": "ne",
}

CODE_TO_LANGUAGE: Dict[str, str] = {value: key for key, value in LANGUAGE_TO_CODE.items()}
LANGUAGE_CODE_ALIASES: Dict[str, str] = {
    "zh": "zh-cn",
}

# Display name -> speech_recognition locale code for Google Web Speech
LANGUAGE_TO_SPEECH_LOCALE: Dict[str, str] = {
    "Spanish": "es-ES",
    "Hindi": "hi-IN",
    "English": "en-US",
    "French": "fr-FR",
    "German": "de-DE",
    "Arabic": "ar-SA",
    "Russian": "ru-RU",
    "Mandarin (Chinese)": "zh-CN",
    "Portuguese": "pt-PT",
    "Italian": "it-IT",
    "Japanese": "ja-JP",
    "Korean": "ko-KR",
    "Bengali": "bn-IN",
    "Marathi": "mr-IN",
    "Telugu": "te-IN",
    "Tamil": "ta-IN",
    "Gujarati": "gu-IN",
    "Urdu": "ur-PK",
    "Kannada": "kn-IN",
    "Odia": "or-IN",
    "Malayalam": "ml-IN",
    "Nepali": "ne-NP",
}

# googletrans code -> Sarvam language code
# Sarvam currently focuses on Indian languages + English, so unsupported
# languages naturally fall back to googletrans.
GOOGLE_TO_SARVAM_CODE: Dict[str, str] = {
    "en": "en-IN",
    "hi": "hi-IN",
    "bn": "bn-IN",
    "mr": "mr-IN",
    "te": "te-IN",
    "ta": "ta-IN",
    "gu": "gu-IN",
    "ur": "ur-IN",
    "kn": "kn-IN",
    "or": "od-IN",
    "ml": "ml-IN",
    "ne": "ne-NP",
}

AUTO_DETECT_LABEL = "Auto Detect"
GOOGLE_ENGINE_LABEL = "Google"
SARVAM_ENGINE_LABEL = "Sarvam"


def get_language_names() -> List[str]:
    return list(LANGUAGE_TO_CODE.keys())


def get_google_language_code(language_name: str) -> str:
    if language_name not in LANGUAGE_TO_CODE:
        raise KeyError(f"Unsupported language: {language_name}")
    return LANGUAGE_TO_CODE[language_name]


def get_speech_locale(language_name: str) -> str:
    if language_name not in LANGUAGE_TO_SPEECH_LOCALE:
        raise KeyError(f"Speech locale unavailable for language: {language_name}")
    return LANGUAGE_TO_SPEECH_LOCALE[language_name]


def get_all_speech_locales() -> List[str]:
    return list(dict.fromkeys(LANGUAGE_TO_SPEECH_LOCALE.values()))


def get_language_name_from_code(code: str) -> str:
    if not code:
        return "Unknown"
    normalized = code.strip().lower()
    normalized = LANGUAGE_CODE_ALIASES.get(normalized, normalized)
    if normalized not in CODE_TO_LANGUAGE and "-" in normalized:
        normalized = normalized.split("-")[0]
        normalized = LANGUAGE_CODE_ALIASES.get(normalized, normalized)
    return CODE_TO_LANGUAGE.get(normalized, normalized)


def get_sarvam_code(google_language_code: str) -> str | None:
    if not google_language_code:
        return None
    return GOOGLE_TO_SARVAM_CODE.get(google_language_code.strip().lower())


def get_source_language_options() -> List[str]:
    return [AUTO_DETECT_LABEL] + get_language_names()


def get_translation_engine_options() -> List[str]:
    return [GOOGLE_ENGINE_LABEL, SARVAM_ENGINE_LABEL]


def get_status_color(status_state: str) -> Tuple[str, str]:
    state = status_state.lower().strip()
    if state == "listening":
        return "#1db954", "Listening"
    if state == "processing":
        return "#2e86de", "Processing"
    if state == "error":
        return "#e74c3c", "Error"
    return "#95a5a6", "Idle"


def timestamp_now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
