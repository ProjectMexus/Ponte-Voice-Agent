// A visual replay of recorded service events. This module never sends actions,
// clicks controls, moves keyboard focus, or reconstructs historical tool results.
const FIELD_GROUPS = {
  departments: ["service", "service_"],
  services: ["service", "service_"],
  cash: ["plan_name", "year", "plan_status", "eligibility", "amount", "payment_status", "scheduled_date"],
  slots: ["slot_", "time", "date"],
  appointments: ["appointment_", "appointments_fetched_at"],
  draft: ["candidate_id", "time", "date"],
  conflict: ["conflict_result"],
  confirmation: ["patient_id", "time", "conflict_result"],
  receipt: ["receipt_id", "reference", "booking_status"],
  recovery: ["message", "explanation", "reason"],
};
const EVENT_GROUPS = {
  options_presented: "slots", draft_prepared: "draft", selection_resolved: "draft",
  booking_interrupted: "appointments", booking_resumed: "draft",
  conflicts_checked: "conflict", confirmation_ready: "confirmation",
  receipt_verified: "receipt", clarification: "recovery", needs_attention: "recovery",
};

export function createAgentMotion({
  root, strip, title, detail, pointer, skipButton, replayButton,
  reducedMotion = () => globalThis.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true,
  schedule = (callback, delay) => setTimeout(callback, delay),
  unschedule = (timer) => clearTimeout(timer),
} = {}) {
  const seen = new Set();
  const timers = new Set();
  let generation = 0;
  let highlighted = [];
  let lastBatch = [];
  let active = false;

  function later(callback, delay, token) {
    const timer = schedule(() => {
      timers.delete(timer);
      if (token === generation) callback();
    }, delay);
    timers.add(timer);
  }

  function clearHighlights() {
    highlighted.forEach((node) => node.classList.remove("agent-pointed"));
    highlighted = [];
  }

  function cancel() {
    generation += 1;
    timers.forEach(unschedule);
    timers.clear();
    clearHighlights();
    active = false;
    if (strip) strip.hidden = true;
    if (pointer) pointer.hidden = true;
    root?.classList.remove("is-agent-replaying");
  }

  function targetsFor(event) {
    if (event.kind === "constraints_updated") {
      return Array.from(root.querySelectorAll(".agent-context-row"));
    }
    const group = Object.hasOwn(FIELD_GROUPS, event.operation) ? event.operation : EVENT_GROUPS[event.kind];
    const keys = Object.hasOwn(FIELD_GROUPS, group) ? FIELD_GROUPS[group] : [];
    const fields = Array.from(root.querySelectorAll("[data-field-key]"))
      .filter((node) => node.tagName !== "BUTTON");
    return keys.flatMap((key) => fields.filter((node) => key.endsWith("_")
      ? node.dataset.fieldKey?.startsWith(key) : node.dataset.fieldKey === key));
  }

  function moveTo(node) {
    if (!pointer || !node?.getBoundingClientRect || !root?.getBoundingClientRect) return;
    const bounds = root.getBoundingClientRect();
    const target = node.getBoundingClientRect();
    const x = Math.max(12, Math.min(bounds.width - 72, target.left - bounds.left + Math.min(36, target.width / 3)));
    const y = Math.max(24, Math.min(bounds.height - 44, target.top - bounds.top + target.height / 2));
    pointer.style.transform = `translate3d(${x}px, ${y}px, 0)`;
  }

  function start(events) {
    cancel();
    if (!events.length || !root || root.hidden || !strip || reducedMotion()) return false;
    const token = generation;
    const stepMs = Math.min(850, 4200 / events.length);
    active = true;
    root.classList.add("is-agent-replaying");
    strip.hidden = false;
    if (pointer) {
      pointer.hidden = false;
      pointer.style.transform = "translate3d(36px, 68px, 0)";
    }
    function step(index) {
      if (index >= events.length || reducedMotion()) { cancel(); return; }
      const event = events[index];
      clearHighlights();
      title.textContent = event.title;
      detail.textContent = event.detail || "";
      strip.dataset.status = event.status || "completed";
      strip.dataset.eventKind = event.kind || "";
      const targets = event.status === "failed" ? [] : targetsFor(event);
      const target = targets[0] || detail;
      later(() => moveTo(target), 30, token);
      later(() => {
        highlighted = targets.length ? targets : [detail];
        highlighted.forEach((node) => node.classList.add("agent-pointed"));
      }, Math.min(240, stepMs / 2), token);
      later(() => step(index + 1), stepMs, token);
    }
    step(0);
    return true;
  }

  function play(response) {
    cancel();
    if (Object.hasOwn(response || {}, "workspace") && !response.workspace) {
      lastBatch = [];
      if (replayButton) replayButton.hidden = true;
      return false;
    }
    const taskId = response?.task?.task_id || "";
    const events = Array.isArray(response?.workspace?.activity) ? response.workspace.activity : [];
    const fresh = events.filter((event) => {
      if (typeof event?.id !== "string" || typeof event?.title !== "string") return false;
      const key = `${taskId}|${event.id}`;
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    if (!fresh.length) return false;
    lastBatch = fresh;
    if (replayButton) replayButton.hidden = reducedMotion();
    return start(fresh);
  }

  function reset() {
    cancel();
    seen.clear();
    lastBatch = [];
    if (replayButton) replayButton.hidden = true;
  }

  skipButton?.addEventListener("click", cancel);
  replayButton?.addEventListener("click", () => start(lastBatch));
  // Let the user's actual click proceed to its original handler. No pointerdown
  // cleanup: changing layout between press and release could swallow that click.
  root?.addEventListener("click", cancel, {capture: true});
  root?.addEventListener("keydown", cancel, {capture: true});
  return {play, cancel, reset, get active() { return active; }};
}
