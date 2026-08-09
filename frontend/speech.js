function getRecognitionConstructor() {
  return globalThis.SpeechRecognition || globalThis.webkitSpeechRecognition || null;
}

function notify(state, onStateChange) {
  onStateChange?.(state);
}

function cantoneseVoice(voices) {
  return voices.find((voice) => /^(?:yue(?:-|$)|zh-(?:hant-)?hk(?:-|$))/i.test(String(voice.lang).replaceAll("_", "-")))
    || voices.find((voice) => /cantonese|粵語|粤语|廣東話|广东话/i.test(voice.name || ""))
    || null;
}

export function createSpeechController({ onTranscript, onStateChange,
  schedule = (callback, delay) => setTimeout(callback, delay),
  unschedule = (timer) => clearTimeout(timer), voiceWaitMs = 1500,
} = {}) {
  let language = "zh-Hant";
  let speechGeneration = 0;
  let clearVoiceWait = null;

  function cancelSpeech() {
    speechGeneration += 1;
    clearVoiceWait?.();
    clearVoiceWait = null;
    globalThis.speechSynthesis?.cancel();
  }
  const Recognition = getRecognitionConstructor();
  const recognition = Recognition ? new Recognition() : null;
  const supported = Boolean(recognition);

  if (!supported) {
    notify("unsupported", onStateChange);
  }

  if (recognition) {
    recognition.lang = "zh-HK";
    recognition.interimResults = true;
    recognition.continuous = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => notify("listening", onStateChange);
    recognition.onresult = (event) => {
      const text = Array.from(event.results)
        .map((result) => result[0]?.transcript || "")
        .join("")
        .trim();
      const lastResult = event.results[event.results.length - 1];
      onTranscript?.({ text, isFinal: Boolean(lastResult?.isFinal) });
    };
    recognition.onerror = (event) => {
      notify(event.error === "not-allowed" ? "permission-denied" : "error", onStateChange);
    };
    recognition.onend = () => notify("idle", onStateChange);
  }

  return {
    supported,
    setLanguage(locale) {
      cancelSpeech();
      language = locale === "en" ? "en" : "zh-Hant";
      if (recognition) recognition.lang = language === "en" ? "en-US" : "zh-HK";
    },
    start() {
      if (!recognition) return false;
      try {
        recognition.start();
        return true;
      } catch (error) {
        notify("error", onStateChange);
        return false;
      }
    },
    stop() {
      recognition?.stop();
    },
    speak(text, { onEnd } = {}) {
      const speechSynthesis = globalThis.speechSynthesis;
      const Utterance = globalThis.SpeechSynthesisUtterance;
      if (!text || !speechSynthesis || !Utterance) return false;
      try {
        cancelSpeech();
        const token = speechGeneration;
        const utterance = new Utterance(text);
        utterance.lang = language === "en" ? "en-US" : "zh-HK";
        utterance.rate = 0.92;
        utterance.pitch = 1;
        utterance.onend = () => { if (token === speechGeneration) onEnd?.(); };
        utterance.onerror = () => { if (token === speechGeneration) onStateChange?.("audio-error"); };
        let spoken = false;
        const trySpeak = () => {
          if (token !== speechGeneration || spoken) return false;
          const voices = speechSynthesis.getVoices?.() || [];
          const voice = language === "en"
            ? voices.find((item) => /^en-US/i.test(item.lang)) || voices.find((item) => /^en(?:-|$)/i.test(item.lang))
            : cantoneseVoice(voices);
          if (!voice) return false;
          spoken = true;
          clearVoiceWait?.();
          clearVoiceWait = null;
          utterance.voice = voice;
          speechSynthesis.resume?.();
          speechSynthesis.speak(utterance);
          return true;
        };
        if (trySpeak()) return true;
        // Enumeration may arrive after the first user turn. Wait for a real
        // Cantonese voice instead of assigning Mandarin or the system default.
        const voicesChanged = () => {
          try { trySpeak(); } catch { cancelSpeech(); onStateChange?.("audio-error"); }
        };
        speechSynthesis.addEventListener?.("voiceschanged", voicesChanged);
        const timer = schedule(() => {
          if (token !== speechGeneration) return;
          try {
            if (trySpeak()) return;
            cancelSpeech();
            onStateChange?.(language === "en" ? "english-unavailable" : "cantonese-unavailable");
          } catch { cancelSpeech(); onStateChange?.("audio-error"); }
        }, voiceWaitMs);
        clearVoiceWait = () => {
          unschedule(timer);
          speechSynthesis.removeEventListener?.("voiceschanged", voicesChanged);
        };
        // Catch a list that became available while the listener was attached.
        trySpeak();
        return true;
      } catch (error) {
        cancelSpeech();
        return false;
      }
    },
    unlock() {
      globalThis.speechSynthesis?.resume?.();
      const AudioContextClass = globalThis.AudioContext || globalThis.webkitAudioContext;
      if (!AudioContextClass) return false;
      try {
        const context = new AudioContextClass();
        if (context.state === "suspended") context.resume();
        const oscillator = context.createOscillator();
        const gain = context.createGain();
        gain.gain.value = 0.0001;
        oscillator.connect(gain).connect(context.destination);
        oscillator.start();
        oscillator.stop(context.currentTime + 0.03);
        oscillator.addEventListener("ended", () => context.close?.(), { once: true });
        return true;
      } catch (error) {
        return false;
      }
    },
    stopSpeaking() {
      cancelSpeech();
    },
  };
}
