from __future__ import annotations

import io
import os
import threading
import webbrowser
from typing import Any, Dict

from flask import Flask, jsonify, make_response, request

from translator import TranslationError, TranslationService
from utils import (
    AUTO_DETECT_LABEL,
    GOOGLE_ENGINE_LABEL,
    get_google_language_code,
    get_language_names,
    get_speech_locale,
    get_translation_engine_options,
    timestamp_now,
)


app = Flask(__name__)

_translation_service = TranslationService()


def _build_history_entry(
    *,
    engine_used: str,
    source_language_name: str,
    target_language_name: str,
    original_text: str,
    translated_text: str,
) -> str:
    return (
        f"[{timestamp_now()}] Engine: {engine_used} | {source_language_name} -> {target_language_name}\n"
        f"Original: {original_text}\n"
        f"Translated: {translated_text}"
    )


@app.get("/")
def index() -> Any:
    # Flask will serve templates/static automatically.
    # We keep this endpoint for convenient open-in-browser behavior.
    return app.send_static_file("index.html")


@app.get("/api/options")
def api_options() -> Any:
    language_names = get_language_names()
    source_language_options = [AUTO_DETECT_LABEL] + language_names
    engine_options = get_translation_engine_options()
    # If Sarvam isn't configured, hide it to avoid a guaranteed failure in demos.
    sarvam_api_key = os.getenv("SARVAM_API_KEY", "").strip()
    if not sarvam_api_key and "Sarvam" in engine_options:
        engine_options = [e for e in engine_options if e != "Sarvam"]

    speech_locales = {}
    for name in language_names:
        speech_locales[name] = get_speech_locale(name)

    # "Auto Detect" doesn't map cleanly for Web Speech, so we still provide a default.
    speech_locales[AUTO_DETECT_LABEL] = get_speech_locale("English")

    return jsonify(
        {
            "languageNames": language_names,
            "sourceLanguageOptions": source_language_options,
            "engineOptions": engine_options,
            "speechLocalesByName": speech_locales,
        }
    )


@app.post("/api/translate")
def api_translate() -> Any:
    payload: Dict[str, Any] = request.get_json(force=True)  # type: ignore[assignment]
    text = str(payload.get("text", "")).strip()
    source_language = str(payload.get("source_language", AUTO_DETECT_LABEL))
    target_language = str(payload.get("target_language", "English"))
    engine = str(payload.get("engine", GOOGLE_ENGINE_LABEL))

    if not text:
        # Validate early so we don't hit external services during failure paths.
        resp = {"error": "No text received for translation."}
        return make_response(jsonify(resp), 400)

    try:
        translation = _translation_service.translate_text(
            text=text,
            target_language_name=target_language,
            source_language_name=source_language,
            preferred_engine=engine,
        )
    except TranslationError as exc:
        resp = {"error": str(exc)}
        return make_response(jsonify(resp), 500)

    detected_name: str = translation.source_language_name or "Unknown"
    entry = _build_history_entry(
        engine_used=translation.engine_used,
        source_language_name=translation.source_language_name,
        target_language_name=translation.target_language_name,
        original_text=translation.original_text,
        translated_text=translation.translated_text,
    )

    return jsonify(
        {
            "originalText": translation.original_text,
            "translatedText": translation.translated_text,
            "detectedLanguageName": detected_name,
            "engineUsed": translation.engine_used,
            "historyEntry": entry,
        }
    )


def _gtts_mp3_bytes(text: str, language_code: str) -> bytes:
    # gTTS uses online services; keep this function isolated so we can fail fast.
    from gtts import gTTS  # local import

    buf = io.BytesIO()
    tts = gTTS(text=text, lang=language_code, slow=False)
    tts.write_to_fp(buf)
    return buf.getvalue()


@app.post("/api/tts")
def api_tts() -> Any:
    payload: Dict[str, Any] = request.get_json(force=True)  # type: ignore[assignment]
    text = str(payload.get("text", "")).strip()
    target_language_name = str(payload.get("target_language", "English"))

    if not text:
        resp = {"error": "Cannot speak empty text."}
        return make_response(jsonify(resp), 400)

    try:
        tts_lang_code = get_google_language_code(target_language_name)
        mp3 = _gtts_mp3_bytes(text=text, language_code=tts_lang_code)
    except Exception as exc:
        resp = {"error": f"Text-to-speech failed: {exc}"}
        return make_response(jsonify(resp), 500)

    response = make_response(mp3)
    response.headers.set("Content-Type", "audio/mpeg")
    return response


def _open_browser(port: int) -> None:
    # Small delay to allow Flask to start.
    import time

    time.sleep(0.6)
    webbrowser.open_new_tab(f"http://127.0.0.1:{port}/")


if __name__ == "__main__":
    # Serve the single-page UI from static assets for simplicity.
    port = 8080
    threading.Thread(target=_open_browser, args=(port,), daemon=True).start()
    app.run(host="0.0.0.0", port=port, debug=False)

