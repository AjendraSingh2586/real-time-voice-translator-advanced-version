let recognition = null;
let listening = false;
let translateSeq = 0;

const el = (id) => document.getElementById(id);

function setStatus({ state, text, detected }) {
  const dot = el("statusDot");
  const spinner = el("spinner");
  const wrap = el("spinnerWrap");

  const colorByState = {
    idle: "#95a5a6",
    listening: "#1db954",
    processing: "#2e86de",
    error: "#e74c3c",
  };

  const stateNorm = (state || "idle").toLowerCase().trim();
  const color = colorByState[stateNorm] || colorByState.idle;
  dot.style.background = color;
  dot.style.boxShadow = `0 0 0 6px ${hexToRgba(color, 0.12)}`;

  el("statusLabel").textContent = `Status: ${text || "Idle"}`;
  if (typeof detected === "string") el("detectedLabel").textContent = `Detected: ${detected || "-"}`;

  if (stateNorm === "listening" || stateNorm === "processing") {
    spinner.style.display = "block";
    spinner.style.borderTopColor = stateNorm === "listening" ? "#1db954" : "#2e86de";
    wrap.style.display = "block";
  } else {
    spinner.style.display = "none";
    wrap.style.display = "block";
  }
}

function hexToRgba(hex, a) {
  const h = hex.replace("#", "");
  const bigint = parseInt(h, 16);
  const r = (bigint >> 16) & 255;
  const g = (bigint >> 8) & 255;
  const b = bigint & 255;
  return `rgba(${r},${g},${b},${a})`;
}

function truncateForLabel(s, max = 70) {
  const t = (s || "").trim();
  if (t.length <= max) return t;
  return `${t.slice(0, max - 3)}...`;
}

async function apiTranslate({ text, source_language, target_language, engine }) {
  const res = await fetch("/api/translate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, source_language, target_language, engine }),
  });
  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.error || "Translation failed");
  }
  return data;
}

async function apiTts({ text, target_language }) {
  const res = await fetch("/api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text, target_language }),
  });
  if (!res.ok) {
    // If TTS fails, still show translation.
    return null;
  }
  const blob = await res.blob();
  return blob;
}

function appendHistory(entry) {
  const hist = el("historyText");
  if (!entry || !entry.trim()) return;
  hist.textContent = `${hist.textContent}${entry}\n\n`;
  hist.scrollTop = hist.scrollHeight;
  // Keep it bounded for demos.
  const maxChars = 9000;
  if (hist.textContent.length > maxChars) {
    hist.textContent = hist.textContent.slice(-maxChars);
  }
}

function clearTextareas() {
  el("originalText").value = "";
  el("translatedText").value = "";
}

function copyText(value) {
  const str = value || "";
  if (!str.trim()) return;
  navigator.clipboard?.writeText(str.trim()).catch(() => {
    // Fallback
    const tmp = document.createElement("textarea");
    tmp.value = str.trim();
    document.body.appendChild(tmp);
    tmp.select();
    document.execCommand("copy");
    document.body.removeChild(tmp);
  });
}

function clearHistory() {
  el("historyText").textContent = "";
}

function stopPlayback() {
  const audio = el("audioPlayer");
  if (!audio) return;
  try {
    audio.pause();
    audio.src = "";
  } catch {
    // ignore
  }
}

function ensureRecognition() {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return null;
  if (recognition) return recognition;

  recognition = new SpeechRecognition();
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.lang = "en-US";

  recognition.onstart = () => {
    listening = true;
    setStatus({ state: "listening", text: "Listening..." });
  };

  recognition.onend = () => {
    listening = false;
    // onend also fires after stop; we let the stop handler set idle state.
  };

  recognition.onerror = (event) => {
    listening = false;
    setStatus({ state: "error", text: event.error || "Speech recognition error" });
  };

  recognition.onresult = async (event) => {
    // Only act on final results to avoid spamming translate.
    let transcript = "";
    let anyFinal = false;
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const res = event.results[i];
      transcript += res[0]?.transcript || "";
      if (res.isFinal) anyFinal = true;
    }

    transcript = transcript.trim();
    if (!transcript) return;
    el("originalText").value = transcript;
    if (!anyFinal) return;

    const seq = ++translateSeq;
    const source_language = el("sourceSelect").value;
    const target_language = el("targetSelect").value;
    const engine = el("engineSelect").value;

    setStatus({ state: "processing", text: "Processing...", detected: "-" });
    el("translatedText").value = "";
    el("speakingLabel").textContent = "Now speaking: -";

    try {
      const data = await apiTranslate({
        text: transcript,
        source_language,
        target_language,
        engine,
      });
      if (seq !== translateSeq) return; // ignore stale responses

      el("translatedText").value = data.translatedText || "";
      el("detectedLabel").textContent = `Detected: ${data.detectedLanguageName || "-"}`;
      appendHistory(data.historyEntry || "");

      const blob = await apiTts({ text: data.translatedText || "", target_language });
      if (seq !== translateSeq) return;
      if (blob) {
        const audio = el("audioPlayer");
        const url = URL.createObjectURL(blob);
        audio.src = url;
        audio.play().catch(() => {});
      }

      el("speakingLabel").textContent = `Now speaking: ${truncateForLabel(data.translatedText) || "-"}`;
      setStatus({ state: "idle", text: "Idle", detected: data.detectedLanguageName || "-" });
    } catch (err) {
      if (seq !== translateSeq) return;
      const full = err?.message || "Translation failed";
      setStatus({ state: "error", text: "Translation failed" });
      appendHistory(`[ERROR] ${full}`);
      el("speakingLabel").textContent = "Now speaking: -";
    }
  };

  return recognition;
}

async function loadOptions() {
  const res = await fetch("/api/options");
  const data = await res.json();

  const sourceSelect = el("sourceSelect");
  const targetSelect = el("targetSelect");
  const engineSelect = el("engineSelect");

  sourceSelect.innerHTML = "";
  for (const name of data.sourceLanguageOptions) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    sourceSelect.appendChild(opt);
  }

  targetSelect.innerHTML = "";
  for (const name of data.languageNames) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    targetSelect.appendChild(opt);
  }
  engineSelect.innerHTML = "";
  for (const name of data.engineOptions) {
    const opt = document.createElement("option");
    opt.value = name;
    opt.textContent = name;
    engineSelect.appendChild(opt);
  }

  // Store mapping for speech recognition language selection.
  window.__speechLocalesByName = data.speechLocalesByName || {};
}

function setControlsRunning(running) {
  el("startBtn").disabled = !!running;
  el("stopBtn").disabled = !running;
  el("sourceSelect").disabled = !!running;
  el("targetSelect").disabled = !!running;
  el("engineSelect").disabled = !!running;
}

async function startListening() {
  const rec = ensureRecognition();
  if (!rec) {
    setStatus({ state: "error", text: "Web Speech API not supported in this browser." });
    return;
  }

  // Reset UI for clean demo.
  translateSeq++;
  clearHistory();
  clearTextareas();
  el("detectedLabel").textContent = "Detected: -";
  el("speakingLabel").textContent = "Now speaking: -";

  setControlsRunning(true);
  stopPlayback();

  const source_language = el("sourceSelect").value;
  const localesByName = window.__speechLocalesByName || {};
  const desiredLocale = localesByName[source_language] || "en-US";
  rec.lang = desiredLocale;

  try {
    rec.start();
  } catch {
    // start() can throw if called twice quickly.
  }
}

function stopListening() {
  translateSeq++;
  setControlsRunning(false);
  setStatus({ state: "idle", text: "Idle" });
  el("speakingLabel").textContent = "Now speaking: -";
  stopPlayback();
  try {
    recognition?.stop();
  } catch {
    // ignore
  }
}

function wire() {
  el("startBtn").addEventListener("click", () => startListening());
  el("stopBtn").addEventListener("click", () => stopListening());

  el("clearHistoryBtn").addEventListener("click", () => clearHistory());
  el("copyOriginalBtn").addEventListener("click", () => copyText(el("originalText").value));
  el("clearOriginalBtn").addEventListener("click", () => (el("originalText").value = ""));
  el("copyTranslatedBtn").addEventListener("click", () => copyText(el("translatedText").value));
  el("clearTranslatedBtn").addEventListener("click", () => (el("translatedText").value = ""));

  window.addEventListener("keydown", (e) => {
    if (e.key === "Escape") stopListening();
    if (e.ctrlKey && (e.key === "Enter" || e.code === "Enter")) startListening();
  });
}

(async function main() {
  try {
    setStatus({ state: "idle", text: "Idle", detected: "-" });
    wire();
    await loadOptions();
  } catch (e) {
    setStatus({ state: "error", text: "Failed to load options." });
    console.error(e);
  }
})();

