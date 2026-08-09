// An English presentation guide. Only server observations advance it;
// this module never constructs, submits, or approves a service action.
export const GUIDE_STEPS = [
  { title: "Find a visit", message: "Book a cardiology appointment next Tuesday afternoon", hint: "Find the department and available times. Your first choice is a draft." },
  { title: "Change the time", message: "Only after 3 PM", hint: "Replace the first draft with a time that fits your new requirement." },
  { title: "Check other bookings", message: "Wait, do I have any other appointments?", hint: "Pause this booking and look up your existing appointments." },
  { title: "Check for a clash", message: "Will that clash with my existing appointments?", hint: "Compare the proposed visit with the appointments just retrieved." },
  { title: "Return to the booking", message: "Go back to the appointment we were booking", hint: "Resume the same task and check the slot is still available." },
  { title: "Choose 15:30", message: "The 3:30 PM one, please", hint: "Request the formal confirmation card. Nothing is booked yet." },
  { title: "Review and approve", message: null, hint: "Check the date and 15:30 time on the confirmation card. Then click its approval button yourself." },
];

const SEARCH = "medical.search_registration_slots";
const APPOINTMENTS = "medical.get_my_appointments";

export function createGuidedDemo({ root, onPreview, onExit, onReview } = {}) {
  let active = false;
  let step = 0;
  let busy = false;
  let mode = "off";
  let connected = false;
  let taskId = null;
  let firstDraft = null;
  let revision = null;
  let secondDraft = null;
  let secondSlotId = null;
  let secondRevision = null;
  let selectionId = null;
  let notice = "";
  const seen = new Set();
  const node = (id) => root ? document.getElementById(id) : null;

  function render() {
    if (!root) return;
    root.hidden = !active;
    const usable = connected && ["scripted", "real"].includes(mode);
    if (!active) return;
    node("guide-mode").textContent = mode === "real" ? "Guided demo · Live LLM"
      : mode === "scripted" ? "Guided demo · Scripted" : "Guided demo · Unavailable";
    node("guide-count").textContent = step === 7 ? "7 of 7 complete" : `Step ${step + 1} of 7`;
    node("guide-title").textContent = step === 7 ? "Booked. Receipt verified." : GUIDE_STEPS[step].title;
    node("guide-hint").textContent = step === 7
      ? "Your simulated 15:30 booking is confirmed. Open the receipt to see the details."
      : GUIDE_STEPS[step].hint;
    node("guide-message").textContent = GUIDE_STEPS[step]?.message || "";
    node("guide-message").hidden = step >= 6;
    node("guide-use").hidden = step >= 6;
    node("guide-use").disabled = busy || !usable;
    node("guide-review").hidden = step !== 6;
    node("guide-review").disabled = busy || !usable || Boolean(notice);
    node("guide-exit").disabled = busy;
    node("guide-edit-hint").hidden = step >= 6;
    node("guide-notice").textContent = !usable
      ? "Connect to a cardiology demo server to continue. No step has been completed."
      : busy ? "Waiting for Ponte…" : notice;
    node("guide-notice").hidden = usable && !busy && !notice;
    const list = node("guide-steps");
    list.replaceChildren();
    GUIDE_STEPS.forEach((item, index) => {
      const li = document.createElement("li");
      li.className = index < step ? "is-done" : index === step ? "is-current" : "";
      if (index === step) li.setAttribute("aria-current", "step");
      const number = document.createElement("span");
      number.className = "guide-step-number";
      number.textContent = index < step ? "✓" : String(index + 1);
      number.setAttribute("aria-hidden", "true");
      const label = document.createElement("span");
      label.textContent = item.title;
      const status = document.createElement("span");
      status.className = "sr-only";
      status.textContent = index < step ? " — complete" : index === step ? " — current" : " — pending";
      li.append(number, label, status);
      list.append(li);
    });
  }

  function reset() {
    step = 0;
    taskId = firstDraft = revision = secondDraft = secondSlotId = secondRevision = selectionId = null;
    notice = "";
    seen.clear();
    render();
  }

  function observe(payload) {
    if (!active || step === 7) return;
    const id = payload?.interaction_id;
    if (!id || seen.has(id)) return;
    seen.add(id);
    const task = payload.task || {};
    const facts = task.facts || {};
    const evidence = facts.demo_observation || {};
    if (task.type !== "medical_demo_agent" || evidence.version !== 1) {
      notice = "This reply cannot verify the guided step. Continue with the suggested message, or exit the guide.";
      render(); return;
    }
    if (taskId && task.task_id !== taskId) {
      notice = "This is a different task. Start a new conversation to restart the guide.";
      render(); return;
    }
    if (payload.recovery || facts.response_reason || ["failed", "cancelled"].includes(task.status)) {
      notice = "This step needs attention. Read Ponte’s reply and clarify or retry; progress has not advanced.";
      render(); return;
    }
    const reads = evidence.successful_reads || [];
    const hasRead = (name) => reads.includes(name);
    const time = (facts.selected_slot?.start || "").slice(11, 16);
    const constraint = facts.time_constraint || {};
    const afterThree = constraint.kind === "lower_bound" && constraint.time === "15:00" && constraint.inclusive === false;
    const sameSelection = Boolean(secondSlotId) && facts.slot_id === secondSlotId
      && facts.intent_revision === secondRevision && time === "15:30" && afterThree;
    const correctDraft = sameSelection && facts.candidate_id === secondDraft;
    const snapshot = facts.appointments_snapshot || {};
    const conflict = facts.conflict_result || {};
    const grounded = Boolean(snapshot.request_id) && Array.isArray(snapshot.records)
      && snapshot.source === APPOINTMENTS && snapshot.task_id === task.task_id
      && conflict.candidate_id === facts.slot_id && conflict.snapshot_request_id === snapshot.request_id
      && ["clear", "overlap"].includes(conflict.status);
    const draft = facts.phase === "awaiting_selection" && facts.candidate_id && !payload.confirmation && !payload.receipt;
    let passed = false;
    if (step === 0) {
      passed = Boolean(draft && time === "14:00" && hasRead("medical.list_departments") && hasRead(SEARCH));
      if (passed) { taskId = task.task_id; firstDraft = facts.candidate_id; revision = facts.intent_revision; }
    } else if (step === 1) {
      passed = Boolean(draft && afterThree && time === "15:30" && facts.candidate_id !== firstDraft
        && facts.intent_revision > revision && hasRead(SEARCH));
      if (passed) { secondDraft = facts.candidate_id; secondSlotId = facts.slot_id; secondRevision = facts.intent_revision; }
    } else if (step === 2) {
      passed = correctDraft && facts.phase === "inquiry" && grounded && hasRead(APPOINTMENTS);
    } else if (step === 3) {
      // The inquiry state alone is insufficient: require the server's validated
      // answer action as well as a conflict result grounded in an actual read.
      passed = correctDraft && facts.phase === "inquiry" && grounded && evidence.control_action === "answer_question";
    } else if (step === 4) {
      // The runtime may replace an expired P2 with P3 after a successful read.
      // Follow the same slot and intent revision, never a changed selection.
      passed = Boolean(sameSelection && draft && grounded && evidence.control_action === "resume_booking" && hasRead(SEARCH));
      if (passed) secondDraft = facts.candidate_id;
    } else if (step === 5) {
      const approve = (payload.workspace?.actions || []).find((item) => item.event?.type === "confirmation_decision" && item.event.decision === "approve");
      passed = sameSelection && grounded && hasRead(SEARCH) && evidence.control_action === "select_slot"
        && facts.phase === "awaiting_approval" && task.status === "awaiting_confirmation"
        && Boolean(payload.confirmation) && Boolean(approve) && !payload.receipt;
      if (passed) { secondDraft = facts.candidate_id; selectionId = facts.slot_id; }
    } else if (step === 6) {
      const receipt = payload.receipt || {};
      const appointment = receipt.appointment || {};
      passed = task.status === "completed" && facts.phase === "completed" && receipt.status === "completed"
        && Boolean(receipt.receipt_id) && receipt.task_id === taskId && appointment.slot_id === selectionId
        && appointment.time === "15:30" && appointment.status === "booked";
    }
    if (passed) { step += 1; notice = ""; }
    else notice = step === 6
      ? "No verified receipt yet. Read Ponte’s reply. If the card expired or changed, start a new conversation or exit the guide."
      : "Ponte has not verified this step yet. Read the reply, then use or clarify the suggested message. You can also exit the guide.";
    render();
  }

  node("guide-use")?.addEventListener("click", () => {
    if (active && !busy && connected && ["scripted", "real"].includes(mode) && step < 6) onPreview?.(GUIDE_STEPS[step].message);
  });
  node("guide-review")?.addEventListener("click", () => { if (active && step === 6 && !busy && !notice) onReview?.(); });
  node("guide-exit")?.addEventListener("click", () => { if (!busy) { active = false; render(); onExit?.(); } });
  render();
  return {
    start() { active = true; reset(); }, reset, observe,
    setBusy(value) { busy = Boolean(value); render(); },
    setConnection(value, demoMode) { connected = Boolean(value); mode = demoMode; render(); },
    reportError() { if (active) { notice = "The request did not finish. Read the error and retry when the service is available; progress has not advanced."; render(); } },
    get active() { return active; }, get step() { return step; },
  };
}
