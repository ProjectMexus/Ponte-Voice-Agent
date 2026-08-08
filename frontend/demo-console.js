// This module presents server state. It never constructs service actions.
export const UI_COPY = {
  "zh-Hant": {
    tagline: "聆聽澳門，連結日常。", newSession: "重新開始", eyebrow: "你的公共服務助手", greeting: "有咩需要？小澳陪你辦。", intro: "從一句話開始，把每一步交代清楚。", prototype: "模擬服務體驗", companion: "與小澳對話", soundOn: "朗讀開啟", soundOff: "朗讀關閉", cantonese: "粵語也可以", withYou: "一步一步，陪你完成", conversation: "對話紀錄", welcome: "你好，我係小澳。", welcomeHint: "想預約醫療服務，還是查詢福利？你可以說話，或在下方打字。", inputLabel: "輸入你的需求", inputPlaceholder: "例如：我想預約醫療服務", inputHint: "Enter 送出 · Shift + Enter 換行", send: "送出", services: "今天想辦甚麼？", chooseHint: "點選情境，預覽你的需求", medical: "醫療預約", medicalHint: "找服務、選時段、確認預約", cash: "現金分享", cashHint: "查看資格與發放資料", appointments: "我的預約", appointmentsHint: "查看日期、時間與地點", workspaceEyebrow: "服務工作區", workspaceHeading: "把需要，變成下一步。", awaiting: "等待你的需求", phaseService: "選擇服務", phaseTime: "挑選時段", phaseConfirm: "確認資料", phaseDone: "取得回執", loading: "小澳正在整理你的需要…", invitationTicket: "你的下一個預約", invitationKicker: "從醫療預約開始體驗", invitationTitle: "你說需要，小澳帶路。", invitationBody: "不用先找對部門。告訴小澳你想辦甚麼，可選服務與時段會在這裡出現。", startDemo: "試試預約醫療服務", invitationNote: "先預覽需求，再由你送出", detailVoice: "說話或打字，都可以", detailVoiceHint: "用你習慣的方式表達需要。", detailControl: "關鍵一步，由你確認", detailControlHint: "看清資料後才提交預約。", detailReceipt: "辦妥後，留下回執", detailReceiptHint: "可以查看、下載或列印。", mockNote: "本次體驗使用模擬資料與服務。", lastReceipt: "查看最近回執", activity: "這次服務的足跡", thisSession: "本次對話", activityEmpty: "送出需求後，每個服務階段都會記錄在這裡。", footer: "讓公共服務，從一句話開始。", resetHeading: "開始新的對話？", resetBody: "畫面上的對話和服務足跡會清除。已提交的模擬預約會保留；未提交的選項不會執行。", resetCancel: "繼續這次對話", resetConfirm: "開始新對話", receiptEyebrow: "服務回執", receiptHeading: "你的預約資料", print: "列印", download: "下載", user: "你", assistant: "小澳", count: "則訊息", awaitingInput: "請選擇下一步", awaitingConfirmation: "需要你的確認", completed: "已完成", cancelled: "已取消", failed: "需要處理", processing: "正在處理", recovery: "需要你的協助", turnOffSound: "關閉自動朗讀", turnOnSound: "開啟自動朗讀",
  },
  en: {
    tagline: "Listen to Macau. Connect everyday life.", newSession: "Start over", eyebrow: "Your public service companion", greeting: "What do you need today?", intro: "Start with a conversation. See every step along the way.", prototype: "Simulated services", companion: "Talk with Ponte", soundOn: "Voice on", soundOff: "Voice off", cantonese: "Cantonese welcome", withYou: "One step at a time", conversation: "Conversation", welcome: "Hello, I’m Ponte.", welcomeHint: "Need a medical appointment or benefit information? Speak to me, or type below.", inputLabel: "Describe what you need", inputPlaceholder: "For example: 我想預約醫療服務", inputHint: "Enter to send · Shift + Enter for a new line", send: "Send", services: "How can we help today?", chooseHint: "Choose a scenario to preview your request", medical: "Book a visit", medicalHint: "Choose a service, time and confirm", cash: "Cash sharing", cashHint: "Check eligibility and payment details", appointments: "My appointments", appointmentsHint: "See the date, time and location", workspaceEyebrow: "Service workspace", workspaceHeading: "Turn a need into a next step.", awaiting: "Waiting for your request", phaseService: "Service", phaseTime: "Time", phaseConfirm: "Review", phaseDone: "Receipt", loading: "Ponte is preparing your next step…", invitationTicket: "Your next appointment", invitationKicker: "Try booking a medical visit", invitationTitle: "Tell us what you need.", invitationBody: "You don’t have to find the right department first. Available services and appointment times will appear here.", startDemo: "Try a medical booking", invitationNote: "Preview your request, then send it", detailVoice: "Speak or type", detailVoiceHint: "Use the way that feels familiar.", detailControl: "You confirm the key step", detailControlHint: "Review the details before booking.", detailReceipt: "Keep a record", detailReceiptHint: "View, download or print your receipt.", mockNote: "This experience uses simulated data and services.", lastReceipt: "View latest receipt", activity: "Your service trail", thisSession: "This conversation", activityEmpty: "Each service stage will appear here after you send a request.", footer: "Public services start with a conversation.", resetHeading: "Start a new conversation?", resetBody: "The conversation and service trail will be cleared. Submitted simulated bookings remain; unsubmitted options will not run.", resetCancel: "Keep this conversation", resetConfirm: "Start new conversation", receiptEyebrow: "Service receipt", receiptHeading: "Your appointment details", print: "Print", download: "Download", user: "You", assistant: "Ponte", count: "messages", awaitingInput: "Choose the next step", awaitingConfirmation: "Your confirmation needed", completed: "Completed", cancelled: "Cancelled", failed: "Needs attention", processing: "Processing", recovery: "Your help is needed", turnOffSound: "Turn voice off", turnOnSound: "Turn voice on",
  },
};

const PHASES = { service_selection: 0, slot_selection: 1, appointment_confirmation: 2, appointment_completed: 3 };
const TERMINAL = new Set(["completed", "cancelled", "failed"]);

export function createDemoConsole({ onSubmit, onMute, onReset } = {}) {
  const byId = (id) => document.getElementById(id);
  const conversation = byId("conversation-log");
  const activity = byId("activity-log");
  const conversationEmpty = byId("conversation-empty")?.cloneNode(true);
  const activityEmpty = byId("activity-empty")?.cloneNode(true);
  const input = byId("message-input");
  const form = byId("message-form");
  let busy = false;
  let muted = false;
  let locale = "zh-Hant";
  let messageCount = 0;
  let latestWorkspace = null;
  let lastActivityKey = null;
  const copy = () => UI_COPY[locale];

  function renderMute() {
    const button = byId("speech-toggle");
    button?.setAttribute("aria-pressed", String(!muted));
    button?.setAttribute("aria-label", muted ? copy().turnOnSound : copy().turnOffSound);
    const label = button?.querySelector("[data-copy]");
    if (label) label.textContent = muted ? copy().soundOff : copy().soundOn;
  }

  function renderCount() {
    const counter = byId("turn-count");
    if (counter) counter.textContent = `${messageCount} ${copy().count}`;
  }

  function setLocale(value) {
    if (!UI_COPY[value]) return;
    locale = value;
    document.querySelectorAll("[data-copy]").forEach((node) => {
      const text = copy()[node.dataset.copy];
      if (text) node.textContent = text;
    });
    document.querySelectorAll("[data-placeholder]").forEach((node) => {
      node.placeholder = copy()[node.dataset.placeholder] || "";
    });
    conversation?.setAttribute("aria-label", copy().conversation);
    byId("workflow-progress")?.setAttribute("aria-label", locale === "en" ? "Medical booking progress" : "醫療預約進度");
    document.querySelectorAll(".message-speaker").forEach((node) => { node.textContent = copy()[node.dataset.role] || copy().assistant; });
    renderCount();
    renderMute();
    if (latestWorkspace) renderWorkspaceMeta(latestWorkspace);
  }

  function appendMessage(role, text) {
    const value = String(text || "").trim();
    if (!value || !conversation) return;
    const normalizedRole = role === "user" ? "user" : "assistant";
    byId("conversation-empty")?.remove();
    const message = document.createElement("article");
    message.className = `message message-${normalizedRole}`;
    const meta = document.createElement("div");
    meta.className = "message-meta";
    const speaker = document.createElement("span");
    speaker.className = "message-speaker";
    speaker.dataset.role = normalizedRole;
    speaker.textContent = copy()[normalizedRole];
    const time = document.createElement("time");
    const now = new Date();
    time.dateTime = now.toISOString();
    time.textContent = now.toLocaleTimeString(locale === "en" ? "en-GB" : "zh-HK", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Macau" });
    meta.append(speaker, time);
    const content = document.createElement("p");
    content.className = "message-text";
    content.textContent = value;
    message.append(meta, content);
    conversation.append(message);
    messageCount += 1;
    renderCount();
    conversation.scrollTop = conversation.scrollHeight;
  }

  function renderWorkspaceMeta(payload) {
    const workspace = payload?.workspace;
    const task = payload?.task || {};
    const heading = byId("workspace-heading");
    if (heading) heading.textContent = typeof workspace?.title === "string" ? workspace.title : copy().workspaceHeading;
    const status = byId("task-status");
    const statusKeys = { awaiting_input: "awaitingInput", awaiting_confirmation: "awaitingConfirmation", completed: "completed", cancelled: "cancelled", failed: "failed", running: "processing", awaiting_recovery: "recovery", recovery: "recovery" };
    if (status) {
      status.textContent = copy()[statusKeys[task.status]] || (workspace ? copy().awaitingInput : copy().awaiting);
      status.dataset.status = task.status || "";
    }
    const terminalFailure = ["cancelled", "failed"].includes(task.status);
    const phase = terminalFailure ? undefined : PHASES[workspace?.view];
    const progress = byId("workflow-progress");
    if (progress) {
      // These labels reflect a server-projected view, never a guessed action.
      progress.hidden = Boolean(workspace && phase === undefined);
      progress.querySelectorAll("[data-phase]").forEach((node) => {
        const index = Number(node.dataset.phase);
        const complete = phase !== undefined && (index < phase || (task.status === "completed" && index === phase));
        const active = !complete && index === phase;
        node.classList.toggle("is-active", active);
        node.classList.toggle("is-complete", complete);
        if (active) node.setAttribute("aria-current", "step");
        else node.removeAttribute("aria-current");
        const dot = node.querySelector(".phase-dot");
        if (dot) dot.textContent = complete ? "✓" : String(index + 1);
      });
    }
    const empty = byId("workspace-empty");
    if (empty) empty.hidden = Boolean(workspace || payload?.recovery);
  }

  function updateWorkspace(payload) {
    if (!payload || typeof payload !== "object") return;
    if (Object.hasOwn(payload, "workspace")) latestWorkspace = payload;
    else if (latestWorkspace) latestWorkspace = { ...latestWorkspace, task: payload.task || latestWorkspace.task };
    if (latestWorkspace) renderWorkspaceMeta(latestWorkspace);
    if (payload.receipt) {
      const receiptButton = byId("last-receipt");
      if (receiptButton) receiptButton.hidden = false;
    }
    const title = payload.workspace?.title;
    if (!title || typeof title !== "string" || !activity) return;
    const key = `${payload.task?.task_id || ""}|${payload.workspace.view}|${title}|${payload.task?.status || ""}`;
    if (lastActivityKey === key) return;
    lastActivityKey = key;
    byId("activity-empty")?.remove();
    const item = document.createElement("li");
    item.className = "activity-entry";
    const label = document.createElement("span");
    label.textContent = ["cancelled", "failed"].includes(payload.task?.status) ? `${title} · ${copy()[payload.task.status]}` : title;
    const time = document.createElement("time");
    const now = new Date();
    time.dateTime = now.toISOString();
    time.textContent = now.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Macau" });
    item.append(label, time);
    activity.append(item);
    activity.scrollTop = activity.scrollHeight;
  }

  function setBusy(value) {
    busy = Boolean(value);
    const workspace = byId("service-workspace");
    workspace?.setAttribute("aria-busy", String(busy));
    const loader = byId("workspace-loading");
    if (loader) loader.hidden = !busy;
    if (input) input.readOnly = busy;
    document.querySelectorAll("#send-button, #start-demo, #new-session, [data-prompt]").forEach((node) => { node.disabled = busy; });
    byId("approval-region")?.querySelectorAll("button").forEach((node) => { node.disabled = busy; });
  }

  function preview(prompt) {
    if (busy || !input) return;
    const status = latestWorkspace?.task?.status;
    if (status && !TERMINAL.has(status)) {
      onReset?.(prompt);
      return;
    }
    input.value = prompt;
    input.focus();
    document.querySelectorAll("[data-prompt]").forEach((node) => {
      const selected = node.dataset.prompt === prompt;
      node.classList.toggle("is-selected", selected);
      node.setAttribute("aria-pressed", String(selected));
    });
  }

  function submit(event) {
    event.preventDefault();
    if (busy) return;
    const text = String(input?.value || "").trim();
    if (!text) { input?.focus(); return; }
    onSubmit?.(text);
  }
  form?.addEventListener("submit", submit);
  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) submit(event);
  });
  document.querySelectorAll("[data-prompt]").forEach((node) => node.addEventListener("click", () => preview(node.dataset.prompt)));
  byId("start-demo")?.addEventListener("click", () => preview("我想預約醫療服務"));
  byId("new-session")?.addEventListener("click", () => { if (!busy) onReset?.(); });
  byId("speech-toggle")?.addEventListener("click", () => {
    muted = !muted;
    renderMute();
    onMute?.(muted);
  });

  function reset() {
    conversation?.replaceChildren();
    if (conversationEmpty) conversation?.append(conversationEmpty.cloneNode(true));
    activity?.replaceChildren();
    if (activityEmpty) activity?.append(activityEmpty.cloneNode(true));
    if (input) input.value = "";
    messageCount = 0;
    latestWorkspace = null;
    lastActivityKey = null;
    const receiptButton = byId("last-receipt");
    if (receiptButton) receiptButton.hidden = true;
    renderWorkspaceMeta({});
    setBusy(false);
    setLocale(locale);
  }

  setLocale(locale);
  return { appendMessage, updateWorkspace, setBusy, setLocale, reset, preview, get muted() { return muted; } };
}
