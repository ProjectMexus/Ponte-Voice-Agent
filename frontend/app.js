import { MiddlewareClient, MiddlewareError } from "./mcp-client.js";
import { createSpeechController } from "./speech.js";
import { createVoiceCapture } from "./voice-capture.js";
import { createVoiceExceptions } from "./voice-exceptions.js";
import { createDemoConsole } from "./demo-console.js";
import { createAgentMotion } from "./agent-motion.js";

function makeSessionId() {
  return `S-${Date.now().toString(36)}`;
}

function makeTurnId() {
  return `VT-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function makeInteractionId() {
  return `INT-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function byId(id) {
  return document.getElementById(id);
}

function isAbort(error) {
  return error?.name === "AbortError";
}

function interactionPayload(payload) {
  const result = payload?.result;
  if (result && typeof result === "object" && (result.response || result.workspace || result.task)) return result;
  return payload && typeof payload === "object" ? payload : {};
}

function responseAudioUrl(payload) {
  const interaction = interactionPayload(payload);
  const speechAudio = payload?.speech_audio || interaction.speech_audio;
  if (speechAudio?.status !== "ready") return null;
  return typeof speechAudio.url === "string" && speechAudio.url ? speechAudio.url : null;
}

const DISPLAY_COPY = {
  "zh-Hant": {
    states: {
      ready: ["準備好了", "點按小澳開始說話"],
      "requesting-permission": ["正在準備麥克風", "請允許麥克風權限"],
      listening: ["小澳正在聆聽", "請自然說話，停頓後便會回應"],
      speaking: ["小澳正在聆聽", "繼續說話，或點按頭像停止"],
      stopping: ["正在完成這一輪", "正在整理你的語音"],
      captured: ["正在傳送", "小澳正在接收你的語音"],
      processing: ["處理中", "請稍候"],
      "speaking-response": ["播放中", "點按頭像停止播放"],
      "audio-error": ["未能播放聲音", "請檢查輸出音量後再試"],
      "permission-denied": ["麥克風已被封鎖", "請允許麥克風權限後再試"],
      unsupported: ["正在使用瀏覽器語音", "粵語語音辨識備援已啟用"],
      error: ["暫時未能完成", "請點按小澳再試一次"],
    },
    captions: { user: "你", assistant: "小澳", separator: "：" },
    system: {
      healthChecking: "正在連線",
      healthOnline: "服務可用",
      healthOffline: "服務暫不可用",
      connectionChecking: "正在檢查語音服務",
      voiceCloud: "雲端語音已就緒",
      voiceFallback: "瀏覽器語音備援",
      voiceUnavailable: "語音需要設定",
      middlewareOffline: "服務未連線",
      serviceLabel: "服務",
      serviceChecking: "連線中",
      serviceOnline: "已連線",
      serviceOffline: "離線",
      voiceLabel: "語音",
      voiceChecking: "檢查中",
      microphoneLabel: "麥克風",
      microphone: {
        ready: "待命",
        "requesting-permission": "等待權限",
        listening: "聆聽中",
        speaking: "聆聽中",
        stopping: "處理中",
        captured: "處理中",
        processing: "處理中",
        "speaking-response": "播放中",
        unsupported: "瀏覽器辨識",
        "permission-denied": "已封鎖",
        "audio-error": "需要注意",
        error: "需要注意",
      },
      avatarAction: "點按小澳開始或停止語音",
      languageControl: "顯示語言",
    },
  },
  en: {
    states: {
      ready: ["Ready", "Tap Ponte to talk"],
      "requesting-permission": ["Microphone access", "Allow microphone access to begin"],
      listening: ["Ponte is listening", "Speak naturally, then pause"],
      speaking: ["Ponte is listening", "Keep speaking or tap the avatar to stop"],
      stopping: ["Finishing this turn", "Preparing your voice request"],
      captured: ["Sending", "Ponte is receiving your voice"],
      processing: ["Processing", "Please wait"],
      "speaking-response": ["Playing", "Tap the avatar to stop playback"],
      "audio-error": ["Audio unavailable", "Check your output volume and try again"],
      "permission-denied": ["Microphone blocked", "Allow microphone access and try again"],
      unsupported: ["Browser voice active", "Cantonese recognition fallback is enabled"],
      error: ["Something went wrong", "Tap Ponte to try again"],
    },
    captions: { user: "You", assistant: "Ponte", separator: ": " },
    system: {
      healthChecking: "Connecting",
      healthOnline: "Service available",
      healthOffline: "Service unavailable",
      connectionChecking: "Checking voice service",
      voiceCloud: "Cloud voice ready",
      voiceFallback: "Browser voice fallback",
      voiceUnavailable: "Voice setup needed",
      middlewareOffline: "Service offline",
      serviceLabel: "Service",
      serviceChecking: "Connecting",
      serviceOnline: "Connected",
      serviceOffline: "Offline",
      voiceLabel: "Voice",
      voiceChecking: "Checking",
      microphoneLabel: "Microphone",
      microphone: {
        ready: "Standby",
        "requesting-permission": "Awaiting access",
        listening: "Listening",
        speaking: "Listening",
        stopping: "Processing",
        captured: "Processing",
        processing: "Processing",
        "speaking-response": "Playing",
        unsupported: "Browser recognition",
        "permission-denied": "Blocked",
        "audio-error": "Needs attention",
        error: "Needs attention",
      },
      avatarAction: "Tap Ponte to start or stop voice",
      languageControl: "Display language",
    },
  },
};

export function startPonteApp() {
  const client = new MiddlewareClient();
  let sessionId = makeSessionId();
  const ponteButton = byId("ponte-button");
  const avatar = byId("ponte-avatar");
  const voiceState = byId("voice-state");
  const meterFill = byId("voice-meter-fill");
  const voiceStatusLabel = byId("voice-status-label");
  const voiceStatusHint = byId("voice-status-hint");
  const captionLine = byId("caption-line");
  const serviceStatusLabel = byId("service-status-label");
  const serviceStatusValue = byId("service-status-value");
  const voicePathLabel = byId("voice-path-label");
  const voicePathValue = byId("voice-path-value");
  const microphoneStatusLabel = byId("microphone-status-label");
  const microphoneStatusValue = byId("microphone-status-value");
  let activeAudio = null;
  let activeRequest = null;
  let latestTurn = 0;
  let recordedTranscript = "";
  let recognitionOnly = false;
  let backendVoiceReady = false;
  let activeSpeechTurn = 0;
  let displayLocale = "zh-Hant";
  let currentState = "ready";
  let currentCaption = null;
  let captionTimer = null;
  let healthSnapshot = { reachable: null, voiceReady: null, demoMode: "off" };
  let lastResponse = null;
  let resetPrompt = null;

  function copy() {
    return DISPLAY_COPY[displayLocale];
  }

  function renderCaption() {
    if (!captionLine || !currentCaption?.text) {
      if (captionLine) captionLine.textContent = "";
      return;
    }
    const captions = copy().captions;
    captionLine.textContent = `${captions[currentCaption.role]}${captions.separator}${currentCaption.text}`;
  }

  function setCaption(role, text) {
    const value = String(text || "").trim();
    clearTimeout(captionTimer);
    captionTimer = null;
    currentCaption = value ? { role, text: value } : null;
    renderCaption();
    if (value) {
      captionTimer = setTimeout(() => {
        currentCaption = null;
        captionTimer = null;
        renderCaption();
      }, 8000);
    }
  }

  function showUserSpeech(text) {
    setCaption("user", text);
  }

  function showPonteReply(text) {
    setCaption("assistant", text);
  }

  // A project can provide another same-origin asset without changing markup.
  const configuredAvatar = globalThis.PONTE_AVATAR_URL;
  if (typeof configuredAvatar === "string" && configuredAvatar.startsWith("/")) avatar.src = configuredAvatar;
  avatar.addEventListener("error", () => { avatar.src = avatar.dataset.defaultAvatar; }, { once: true });

  function renderSystemStatus() {
    const system = copy().system;
    const health = byId("health-status");
    const connection = byId("connection-label");
    const reachable = healthSnapshot.reachable;
    const voiceReady = healthSnapshot.voiceReady;

    health.textContent = reachable === null
      ? system.healthChecking
      : (reachable ? system.healthOnline : system.healthOffline);
    if (reachable && healthSnapshot.demoMode === "scripted") {
      health.textContent += displayLocale === "en" ? " · Scripted demo" : " · 腳本模型示範";
    } else if (reachable && healthSnapshot.demoMode === "real") {
      health.textContent += displayLocale === "en" ? " · Live model demo" : " · 即時模型示範";
    }
    health.classList.toggle("is-offline", reachable === false);
    connection.textContent = reachable === null
      ? system.connectionChecking
      : (!reachable
        ? system.middlewareOffline
        : (voiceReady ? system.voiceCloud : (speech.supported ? system.voiceFallback : system.voiceUnavailable)));

    serviceStatusLabel.textContent = system.serviceLabel;
    serviceStatusValue.textContent = reachable === null
      ? system.serviceChecking
      : (reachable ? system.serviceOnline : system.serviceOffline);
    if (reachable && healthSnapshot.demoMode === "scripted") {
      serviceStatusValue.textContent += displayLocale === "en" ? " · Scripted demo" : " · 腳本模型示範";
    } else if (reachable && healthSnapshot.demoMode === "real") {
      serviceStatusValue.textContent += displayLocale === "en" ? " · Live model demo" : " · 即時模型示範";
    }
    voicePathLabel.textContent = system.voiceLabel;
    voicePathValue.textContent = reachable === null
      ? system.voiceChecking
      : (!reachable
        ? system.middlewareOffline
        : (voiceReady ? system.voiceCloud : (speech.supported ? system.voiceFallback : system.voiceUnavailable)));
    microphoneStatusLabel.textContent = system.microphoneLabel;
    microphoneStatusValue.textContent = system.microphone[currentState] || system.microphone.ready;
  }

  function setState(state, { level = null } = {}) {
    currentState = state;
    document.body.dataset.voiceState = state;
    ponteButton.setAttribute("aria-pressed", String(["requesting-permission", "listening", "speaking", "processing", "speaking-response"].includes(state)));
    const [visibleLabel, visibleHint] = copy().states[state] || copy().states.ready;
    voiceState.textContent = `${visibleLabel} ${visibleHint}`;
    voiceStatusLabel.textContent = visibleLabel;
    voiceStatusHint.textContent = visibleHint;
    microphoneStatusValue.textContent = copy().system.microphone[state] || copy().system.microphone.ready;
    if (level !== null) meterFill.style.transform = `scaleX(${Math.max(0.03, Math.min(1, level))})`;
  }

  function setDisplayLocale(locale) {
    if (!DISPLAY_COPY[locale]) return;
    displayLocale = locale;
    document.documentElement.lang = locale;
    byId("language-toggle").setAttribute("aria-label", copy().system.languageControl);
    document.querySelectorAll("[data-locale]").forEach((button) => {
      const active = button.dataset.locale === locale;
      button.classList.toggle("is-active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    ponteButton.setAttribute("aria-label", copy().system.avatarAction);
    avatar.alt = displayLocale === "zh-Hant" ? "小澳" : "Ponte";
    byId("avatar-action-label").textContent = copy().system.avatarAction;
    setState(currentState);
    renderSystemStatus();
    renderCaption();
    agentMotion.cancel();
    consoleView.setLocale(locale);
    if (lastResponse) exceptions.renderResponse(lastResponse);
  }

  function stopPlayback() {
    activeAudio?.pause();
    if (activeAudio) activeAudio.currentTime = 0;
    activeAudio = null;
    activeSpeechTurn = 0;
    speech.stopSpeaking();
  }

  function interruptCurrentTurn() {
    agentMotion.cancel();
    activeRequest?.abort();
    activeRequest = null;
    stopPlayback();
  }

  async function playResponse(payload, turn) {
    if (turn !== latestTurn) return;
    const interaction = interactionPayload(payload);
    const response = interaction.response || {};
    const displayText = typeof response.display_text === "string" ? response.display_text.trim() : "";
    const speechText = typeof response.speech_text === "string" ? response.speech_text.trim() : "";
    showPonteReply(displayText);
    consoleView.appendMessage("assistant", displayText);
    if (consoleView.muted || !speechText) {
      setState("ready");
      return;
    }
    const audioUrl = responseAudioUrl(payload);
    if (audioUrl) {
      const audio = new Audio(client.absoluteUrl(audioUrl));
      activeAudio = audio;
      let browserFallbackStarted = false;
      audio.addEventListener("ended", () => {
        if (activeAudio === audio) {
          activeAudio = null;
          setState("ready");
        }
      }, { once: true });
      const fallbackToBrowserSpeech = () => {
        if (browserFallbackStarted || turn !== latestTurn || consoleView.muted || activeAudio !== audio) return;
        browserFallbackStarted = true;
        if (activeAudio === audio) activeAudio = null;
        activeSpeechTurn = turn;
        const speechStarted = speechText && speech.speak(speechText, { onEnd: () => {
          if (turn === latestTurn) {
            activeSpeechTurn = 0;
            setState("ready");
          }
        } });
        if (speechStarted) {
          setState("speaking-response");
          return;
        }
        activeSpeechTurn = 0;
        if (turn === latestTurn) {
          exceptions.renderError({ message: "未能播放 Ponte 的聲音。請檢查瀏覽器音訊權限與系統輸出裝置。" });
          setState("audio-error");
        }
      };
      audio.addEventListener("error", fallbackToBrowserSpeech, { once: true });
      try {
        await audio.play();
        if (turn === latestTurn && activeAudio === audio && !consoleView.muted) setState("speaking-response");
        return;
      } catch {
        fallbackToBrowserSpeech();
        return;
      }
    }
    activeSpeechTurn = turn;
    const speechStarted = speechText && speech.speak(speechText, { onEnd: () => {
      if (turn === latestTurn) {
        activeSpeechTurn = 0;
        setState("ready");
      }
    } });
    if (speechStarted) {
      setState("speaking-response");
      return;
    }
    activeSpeechTurn = 0;
    if (turn === latestTurn) {
      // Text delivery remains usable when this browser has no speech output.
      setState("ready");
    }
  }

  async function submitVoice(clip, transcript = "") {
    agentMotion.cancel();
    const turn = ++latestTurn;
    activeRequest?.abort();
    const controller = new AbortController();
    activeRequest = controller;
    exceptions.clearError();
    consoleView.setBusy(true);
    setState("processing");
    showUserSpeech(transcript);
    try {
      const payload = await client.sendVoiceTurn({
        sessionId,
        turnId: makeTurnId(),
        audio: clip.blob,
        signal: controller.signal,
      });
      if (turn !== latestTurn) return;
      consoleView.appendMessage("user", transcript || (displayLocale === "en" ? "Voice request sent" : "已送出語音需求"));
      renderDelivery(payload);
      await playResponse(payload, turn);
    } catch (error) {
      if (turn !== latestTurn || isAbort(error)) return;
      // When cloud STT is not configured, use the browser recognizer transcript
      // instead of leaving the user with a silent 503 voice turn.
      if (!backendVoiceReady && transcript && speech.supported) {
        recognitionOnly = false;
        await submitTranscript(transcript);
        return;
      }
      exceptions.renderError(error instanceof MiddlewareError ? error : { message: "語音傳送未完成，請再試一次。" });
      setState("error");
    } finally {
      if (turn === latestTurn) { activeRequest = null; consoleView.setBusy(false); }
    }
  }

  async function submitTranscript(text) {
    const transcript = String(text || "").trim();
    if (!transcript) return;
    agentMotion.cancel();
    recognitionOnly = false;
    capture.cancel();
    speech.stop();
    stopPlayback();
    const turn = ++latestTurn;
    activeRequest?.abort();
    const controller = new AbortController();
    activeRequest = controller;
    exceptions.clearError();
    consoleView.setBusy(true);
    setState("processing");
    showUserSpeech(transcript);
    consoleView.appendMessage("user", transcript);
    try {
      const payload = await client.sendInteraction({
        routing: { interaction_id: makeInteractionId(), session_id: sessionId },
        event: { type: "user_utterance", task_id: null, content: transcript },
      }, { signal: controller.signal });
      if (turn !== latestTurn) return;
      renderDelivery(payload);
      byId("message-input").value = "";
      await playResponse(payload, turn);
    } catch (error) {
      if (turn !== latestTurn || isAbort(error)) return;
      exceptions.renderError(error instanceof MiddlewareError ? error : { message: "未能送出這次需求，請再試一次。" });
      setState("error");
    } finally {
      if (turn === latestTurn) { activeRequest = null; consoleView.setBusy(false); }
    }
  }

  async function handleAction(event) {
    if (!event || typeof event !== "object" || Array.isArray(event)) return;
    if (activeRequest) return;
    recognitionOnly = false;
    capture.cancel();
    speech.stop();
    interruptCurrentTurn();
    const turn = ++latestTurn;
    const controller = new AbortController();
    activeRequest = controller;
    exceptions.clearError();
    consoleView.setBusy(true);
    setState("processing");
    const clicked = document.activeElement;
    const choice = clicked?.closest?.(".action-button, .workspace-field-action");
    const label = choice?.classList.contains("workspace-field-action")
      ? Array.from(choice.querySelectorAll(".workspace-field-label, .workspace-field-value")).map((node) => node.textContent.trim()).filter(Boolean).join(" · ")
      : choice?.textContent?.trim();
    if (label) consoleView.appendMessage("user", label);
    try {
      const payload = await client.sendInteraction({
        routing: { interaction_id: makeInteractionId(), session_id: sessionId },
        event,
      }, { signal: controller.signal });
      if (turn !== latestTurn) return;
      renderDelivery(payload);
      await playResponse(payload, turn);
      if (turn === latestTurn && choice && !choice.isConnected) {
        const focused = document.activeElement;
        if (!focused || focused === document.body || !focused.isConnected) {
          const title = !byId("service-workspace").hidden ? byId("workspace-heading") : byId("message-input");
          title?.focus();
        }
      }
    } catch (error) {
      if (turn !== latestTurn || isAbort(error)) return;
      exceptions.renderError(error instanceof MiddlewareError ? error : { message: "暫時未能完成這項服務，請重試。" });
      setState("error");
    } finally {
      if (turn === latestTurn) { activeRequest = null; consoleView.setBusy(false); }
    }
  }

  const agentMotion = createAgentMotion({
    root: byId("service-workspace"),
    strip: byId("operation-replay"),
    title: byId("operation-title"),
    detail: byId("operation-detail"),
    pointer: byId("agent-cursor"),
    skipButton: byId("operation-skip"),
    replayButton: byId("replay-operations"),
  });

  const exceptions = createVoiceExceptions({
    approvalRoot: byId("approval-region"),
    errorRoot: byId("global-error"),
    artifactRoot: byId("artifact-drawer"),
    artifactContentRoot: byId("artifact-content"),
    onAction: handleAction,
  });

  const speech = createSpeechController({
    onTranscript({ text, isFinal }) {
      recordedTranscript = text || recordedTranscript;
      showUserSpeech(recordedTranscript);
      if (recognitionOnly && isFinal) submitTranscript(recordedTranscript);
    },
    onStateChange(state) {
      if (recognitionOnly && state === "listening") setState("listening");
      if (recognitionOnly && state === "permission-denied") setState("permission-denied");
      if (state === "audio-error" && activeSpeechTurn === latestTurn && document.body.dataset.voiceState === "speaking-response") {
        exceptions.renderError({ message: "瀏覽器未能播放聲音。請檢查系統輸出裝置與音量，然後再試一次。" });
        setState("audio-error");
      }
    },
  });

  const capture = createVoiceCapture();

  function renderDelivery(payload) {
    lastResponse = interactionPayload(payload);
    exceptions.renderResponse(lastResponse);
    consoleView.updateWorkspace(lastResponse);
    consoleView.setBusy(true);
    agentMotion.play(lastResponse);
    healthSnapshot.reachable = true;
    renderSystemStatus();
  }

  function requestNewSession(prompt = null) {
    if (activeRequest) return;
    resetPrompt = typeof prompt === "string" ? prompt : null;
    byId("reset-dialog").showModal();
  }

  const consoleView = createDemoConsole({
    onSubmit: submitTranscript,
    onMute(muted) {
      if (muted) { stopPlayback(); if (currentState === "speaking-response") setState("ready"); }
    },
    onReset: requestNewSession,
  });
  byId("reset-cancel").addEventListener("click", () => { resetPrompt = null; byId("reset-dialog").close(); });
  byId("reset-confirm").addEventListener("click", () => {
    latestTurn += 1;
    recognitionOnly = false;
    capture.cancel();
    speech.stop();
    interruptCurrentTurn();
    sessionId = makeSessionId();
    lastResponse = null;
    exceptions.reset();
    consoleView.reset();
    agentMotion.reset();
    setCaption(null, "");
    setState("ready");
    byId("reset-dialog").close();
    if (resetPrompt) consoleView.preview(resetPrompt);
    resetPrompt = null;
  });
  byId("last-receipt").addEventListener("click", () => exceptions.openArtifact());

  async function startVoiceTurn() {
    interruptCurrentTurn();
    recordedTranscript = "";
    recognitionOnly = false;
    if (!backendVoiceReady && speech.supported) {
      recognitionOnly = true;
      setState("unsupported");
      speech.start();
      return;
    }
    if (capture.supported) {
      // Recognition is optional: it improves accessibility and provides a
      // transcript while the recorded clip remains the authoritative turn.
      if (speech.supported) speech.start();
      await capture.start({
        onStateChange(state) { setState(state); },
        onLevel(level) { setState(document.body.dataset.voiceState || "listening", { level }); },
        onComplete(clip) {
          speech.stop();
          submitVoice(clip, recordedTranscript);
        },
        onFailure(error) {
          if (speech.supported) {
            recognitionOnly = true;
            setState("unsupported");
            speech.start();
          } else {
            exceptions.renderError({ message: error?.name === "NotAllowedError" ? "請允許麥克風權限後再試一次。" : "這個瀏覽器未能開始錄音。" });
            setState("error");
          }
        },
      });
      return;
    }
    if (speech.supported) {
      recognitionOnly = true;
      setState("unsupported");
      speech.start();
    } else {
      exceptions.renderError({ message: "請使用支援麥克風錄音或語音辨識的瀏覽器。" });
      setState("error");
    }
  }

  ponteButton.addEventListener("click", () => {
    if (activeRequest) return;
    // A user gesture is required before some browsers allow speech/audio output.
    speech.unlock?.();
    const state = document.body.dataset.voiceState;
    if (state === "speaking-response") {
      latestTurn += 1;
      interruptCurrentTurn();
      setState("ready");
      return;
    }
    if (["listening", "speaking", "requesting-permission"].includes(state)) {
      capture.stop("manual");
      speech.stop();
      return;
    }
    startVoiceTurn();
  });

  document.querySelectorAll("[data-locale]").forEach((button) => {
    button.addEventListener("click", () => setDisplayLocale(button.dataset.locale));
  });

  client.health()
    .then((payload) => {
      const reachable = payload.backend_reachable !== false;
      backendVoiceReady = payload.voice_ready !== false;
      healthSnapshot = { reachable, voiceReady: backendVoiceReady, demoMode: payload.demo_agent_mode || "off" };
      renderSystemStatus();
    })
    .catch(() => {
      backendVoiceReady = false;
      healthSnapshot = { reachable: false, voiceReady: false };
      renderSystemStatus();
    });

  setDisplayLocale("zh-Hant");
  return { client, get sessionId() { return sessionId; }, capture, speech, consoleView, submitTranscript, submitVoice, handleAction, interruptCurrentTurn };
}

if (typeof document !== "undefined") {
  document.addEventListener("DOMContentLoaded", startPonteApp, { once: true });
}
