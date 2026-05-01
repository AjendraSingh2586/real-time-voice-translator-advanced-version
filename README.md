🌍 Real-Time Multilingual Voice Translator

A Python-based real-time speech-to-speech translator with auto language detection, dual translation engines, and a responsive threaded UI.

🚀 Features
🎤 Real-time speech input with noise adjustment
🧠 Auto language detection
🌐 Translation (Google + Sarvam with fallback)
🔊 Instant text-to-speech output
🖥️ Modern dark UI (Tkinter)
⚡ Multithreaded (no UI freezing)
📝 Translation history with timestamps
🌐 Languages Supported

22 languages including English, Hindi, Spanish, French, German, Chinese, Arabic, and more.



🧩 Project Structure
voice_translator/
├── main.py
├── speech_input.py
├── translator.py
├── speech_output.py
├── ui.py
├── utils.py


⚙️ Setup
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
▶️ Run
py main.py
⭐ Highlights
Real-time pipeline: Speech → Text → Translate → Speech
Smart fallback system for reliability
Clean modular design + threaded architecture
