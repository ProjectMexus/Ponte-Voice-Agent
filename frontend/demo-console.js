// This module presents server state. It never constructs service actions.
export const UI_COPY = {
  "zh-Hant": {
    operationReplay: "操作回放", skipReplay: "略過", replayOperations: "重播本輪操作", newSession: "重新開始", connectionInfo: "連線與語音", greeting: "今天想辦甚麼？", companion: "對話", soundOn: "朗讀開啟", soundOff: "朗讀關閉", conversation: "對話紀錄", inputLabel: "輸入你的需求", inputPlaceholder: "例如：我想預約醫療服務", inputHint: "Enter 送出 · Shift + Enter 換行", send: "送出", services: "常用服務", medical: "醫療預約", cash: "現金分享", appointments: "我的預約", loading: "處理中…", mockNote: "使用模擬資料。", lastReceipt: "查看回執", activity: "處理紀錄", resetHeading: "開始新的對話？", resetBody: "畫面上的對話和服務足跡會清除。已提交的模擬預約會保留；未提交的選項不會執行。", resetCancel: "繼續這次對話", resetConfirm: "開始新對話", receiptEyebrow: "服務回執", receiptHeading: "預約回執", print: "列印", download: "下載", user: "你", assistant: "小澳", count: "則訊息", awaitingInput: "待選擇", awaitingConfirmation: "待確認", completed: "已完成", cancelled: "已取消", failed: "需要處理", processing: "正在處理", recovery: "請補充資料", turnOffSound: "關閉自動朗讀", turnOnSound: "開啟自動朗讀",
  },
  en: {
    operationReplay: "Operation replay", skipReplay: "Skip", replayOperations: "Replay this turn", newSession: "Start over", connectionInfo: "Connection and voice", greeting: "What do you need today?", companion: "Conversation", soundOn: "Voice on", soundOff: "Voice off", conversation: "Conversation", inputLabel: "Describe what you need", inputPlaceholder: "For example: 我想預約醫療服務", inputHint: "Enter to send · Shift + Enter for a new line", send: "Send", services: "Quick requests", medical: "Book a visit", cash: "Cash sharing", appointments: "My appointments", loading: "Processing…", mockNote: "Uses simulated data.", lastReceipt: "View receipt", activity: "Activity", resetHeading: "Start a new conversation?", resetBody: "The conversation and service trail will be cleared. Submitted simulated bookings remain; unsubmitted options will not run.", resetCancel: "Keep this conversation", resetConfirm: "Start new conversation", receiptEyebrow: "Service receipt", receiptHeading: "Appointment receipt", print: "Print", download: "Download", user: "You", assistant: "Ponte", count: "messages", awaitingInput: "Awaiting selection", awaitingConfirmation: "Awaiting confirmation", completed: "Completed", cancelled: "Cancelled", failed: "Needs attention", processing: "Processing", recovery: "More information needed", turnOffSound: "Turn voice off", turnOnSound: "Turn voice on",
  },
};

export function createDemoConsole({ onSubmit, onMute, onReset } = {}) {
  const byId = (id) => document.getElementById(id);
  const conversation = byId("conversation-log");
  const activity = byId("activity-log");
  const conversationEmpty = byId("conversation-empty")?.cloneNode(true);
  const input = byId("message-input");
  const form = byId("message-form");
  let busy = false;
  let muted = false;
  let locale = "zh-Hant";
  let messageCount = 0;
  let latestWorkspace = null;
  let lastActivityKey = null;
  const observedEvents = new Set();
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

  function renderComposer() {
    const value = String(input?.value || "");
    const hasContent = Boolean(value.trim());
    form?.classList.toggle("has-content", hasContent);
    form?.setAttribute("aria-busy", String(busy));
    const send = byId("send-button");
    if (send) send.disabled = busy || !hasContent;
    document.querySelectorAll("[data-prompt]").forEach((node) => {
      const selected = value === node.dataset.prompt;
      node.classList.toggle("is-selected", selected);
      node.setAttribute("aria-pressed", String(selected));
    });
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
    document.querySelectorAll(".message-speaker").forEach((node) => { node.textContent = copy()[node.dataset.role] || copy().assistant; });
    renderCount();
    renderMute();
    renderComposer();
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
    if (heading) heading.textContent = typeof workspace?.title === "string" ? workspace.title : payload?.recovery ? copy().recovery : payload?.receipt ? copy().receiptEyebrow : "";
    renderTaskStatus(payload);
  }

  function renderTaskStatus(payload = latestWorkspace) {
    const status = byId("task-status");
    if (!status) return;
    const task = payload?.task || {};
    const keys = {awaiting_input:"awaitingInput",awaiting_confirmation:"awaitingConfirmation",completed:"completed",cancelled:"cancelled",failed:"failed",running:"processing",awaiting_recovery:"recovery",recovery:"recovery"};
    const kind = busy ? "running" : payload?.recovery ? "recovery" : task.status || "";
    status.textContent = busy ? copy().processing : copy()[keys[kind]] || (payload?.receipt ? copy().completed : payload?.workspace ? copy().awaitingInput : "");
    status.dataset.status = kind;
    status.hidden = !status.textContent || status.textContent === byId("workspace-heading")?.textContent;
  }

  function updateWorkspace(payload) {
    if (!payload || typeof payload !== "object") return;
    if (Object.hasOwn(payload, "workspace")) latestWorkspace = payload;
    else if (payload.recovery) latestWorkspace = { ...payload, workspace: null };
    else if (payload.receipt) latestWorkspace = { ...latestWorkspace, ...payload };
    else if (latestWorkspace) latestWorkspace = { ...latestWorkspace, task: payload.task || latestWorkspace.task };
    if (latestWorkspace) renderWorkspaceMeta(latestWorkspace);
    if (payload.receipt) {
      const receiptButton = byId("last-receipt");
      if (receiptButton) receiptButton.hidden = false;
    }
    const events = payload.workspace?.activity;
    if (Array.isArray(events) && events.length && activity) {
      for (const event of events) {
        if (typeof event?.id !== "string" || typeof event?.title !== "string") continue;
        const key = `${payload.task?.task_id || ""}|${event.id}`;
        if (observedEvents.has(key)) continue;
        observedEvents.add(key);
        const item = document.createElement("li");
        item.className = "activity-entry";
        item.dataset.status = event.status || "completed";
        const content = document.createElement("div");
        content.className = "activity-event-copy";
        const title = document.createElement("strong");
        title.textContent = event.title;
        content.append(title);
        if (typeof event.detail === "string" && event.detail) {
          const detail = document.createElement("p");
          detail.textContent = event.detail;
          content.append(detail);
        }
        const time = document.createElement("time");
        const date = new Date(event.at);
        if (!Number.isNaN(date.getTime())) {
          time.dateTime = date.toISOString();
          time.textContent = date.toLocaleTimeString("en-GB", {hour:"2-digit",minute:"2-digit",timeZone:"Asia/Macau"});
        }
        item.append(content, time);
        activity.append(item);
      }
      const panel = byId("activity-panel");
      if (panel) panel.hidden = !activity.children.length;
      activity.scrollTop = activity.scrollHeight;
      return;
    }
    const title = payload.workspace?.title;
    if (!title || typeof title !== "string" || !activity) return;
    const key = `${payload.task?.task_id || ""}|${payload.workspace.view}|${title}|${payload.task?.status || ""}`;
    if (lastActivityKey === key) return;
    lastActivityKey = key;
    const activityPanel = byId("activity-panel");
    if (activityPanel) activityPanel.hidden = false;
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
    renderTaskStatus();
    const workspace = byId("service-workspace");
    workspace?.setAttribute("aria-busy", String(busy));
    const loader = byId("workspace-loading");
    if (loader) loader.hidden = !busy || !workspace?.hidden;
    if (input) input.readOnly = busy;
    document.querySelectorAll("#new-session, [data-prompt]").forEach((node) => { node.disabled = busy; });
    byId("approval-region")?.querySelectorAll("button").forEach((node) => {
      node.disabled = busy;
      if (!busy) {
        node.classList.remove("is-submitting");
        node.removeAttribute("aria-busy");
      }
    });
    renderComposer();
  }

  function preview(prompt) {
    if (busy || !input) return;
    input.value = prompt;
    renderComposer();
    input.focus();
  }

  function submit(event) {
    event.preventDefault();
    if (busy) return;
    const text = String(input?.value || "").trim();
    if (!text) { input?.focus(); return; }
    onSubmit?.(text);
  }
  form?.addEventListener("submit", submit);
  input?.addEventListener("input", renderComposer);
  input?.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey && !event.isComposing) submit(event);
  });
  document.querySelectorAll("[data-prompt]").forEach((node) => node.addEventListener("click", () => preview(node.dataset.prompt)));
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
    const activityPanel = byId("activity-panel");
    if (activityPanel) activityPanel.hidden = true;
    if (input) input.value = "";
    messageCount = 0;
    latestWorkspace = null;
    lastActivityKey = null;
    observedEvents.clear();
    const receiptButton = byId("last-receipt");
    if (receiptButton) receiptButton.hidden = true;
    renderWorkspaceMeta({});
    setBusy(false);
    setLocale(locale);
  }

  setLocale(locale);
  return { appendMessage, updateWorkspace, setBusy, setLocale, reset, preview, get muted() { return muted; } };
}
