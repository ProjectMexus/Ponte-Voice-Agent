import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { createDOM } from "./helpers/dom-fixture.mjs";
import { createGuidedDemo, GUIDE_STEPS } from "../frontend/guided-demo.js";

let guide, nodes, previews, reviews, exits;
beforeEach(() => {
  const fixture = createDOM();
  globalThis.document = fixture.document;
  nodes = {};
  const root = fixture.add("section", "guided-demo");
  for (const id of ["mode", "count", "title", "hint", "message", "use", "review", "exit", "edit-hint", "notice", "steps"]) {
    nodes[id] = fixture.add(["use", "review", "exit"].includes(id) ? "button" : "div", `guide-${id}`, root);
  }
  previews = []; reviews = 0; exits = 0;
  guide = createGuidedDemo({ root, onPreview: (text) => previews.push(text), onReview: () => reviews++, onExit: () => exits++ });
  guide.setConnection(true, "real");
  guide.start();
});

function response(turn, changes = {}) {
  const phase = turn >= 7 ? "completed" : turn === 6 ? "awaiting_approval" : [3, 4].includes(turn) ? "inquiry" : "awaiting_selection";
  const candidate = turn === 1 ? "P1" : "P2";
  const slotId = turn === 1 ? "slot-1400" : "slot-1530";
  const snapshot = turn >= 3 ? { request_id: "Q1", task_id: "T1", source: "medical.get_my_appointments", records: [] } : null;
  const result = {
    interaction_id: `I${turn}`, response: { display_text: "Assistant prose is not evidence." },
    task: { task_id: "T1", type: "medical_demo_agent", status: turn >= 7 ? "completed" : turn === 6 ? "awaiting_confirmation" : "awaiting_input", facts: {
      phase, candidate_id: candidate, intent_revision: turn === 1 ? 1 : 2, slot_id: slotId,
      selected_slot: { start: `2026-10-20T${turn === 1 ? "14:00" : "15:30"}:00+08:00` },
      time_constraint: turn === 1 ? { kind: "afternoon" } : { kind: "lower_bound", time: "15:00", inclusive: false },
      appointments_snapshot: snapshot,
      conflict_result: { status: "clear", candidate_id: slotId, snapshot_request_id: snapshot?.request_id },
      demo_observation: { version: 1, control_action: ({ 3: "query_appointments", 4: "answer_question", 5: "resume_booking", 6: "select_slot" })[turn],
        successful_reads: ({ 1: ["medical.list_departments", "medical.search_registration_slots"], 2: ["medical.search_registration_slots"], 3: ["medical.get_my_appointments"], 5: ["medical.search_registration_slots"], 6: ["medical.search_registration_slots"] })[turn] || [] },
    } },
    confirmation: turn === 6 ? { confirmation_id: "C1" } : null,
    workspace: { actions: turn === 6 ? [{ event: { type: "confirmation_decision", decision: "approve", action_id: "A1" } }] : [] },
    receipt: turn >= 7 ? { receipt_id: "R1", task_id: "T1", status: "completed", appointment: { slot_id: "slot-1530", time: "15:30", status: "booked" } } : null,
    recovery: null,
  };
  changes(result);
  return result;
}
function advanceThrough(turn) { for (let i = 1; i <= turn; i++) guide.observe(response(i, () => {})); }

test("seven verified responses advance, show the actual model mode, and require the existing card", () => {
  assert.equal(nodes.mode.textContent, "Guided demo · Live LLM");
  for (let i = 1; i <= 6; i++) {
    nodes.use.click();
    assert.equal(previews.at(-1), GUIDE_STEPS[i - 1].message);
    assert.equal(guide.step, i - 1, "previewing a message does not advance");
    guide.observe(response(i, () => {}));
    assert.equal(guide.step, i);
  }
  assert.equal(nodes.use.hidden, true);
  nodes.use.click();
  assert.equal(previews.length, 6, "the guide cannot send an approval message");
  nodes.review.click();
  assert.equal(reviews, 1, "review only focuses the server card");
  assert.equal(guide.step, 6, "review cannot mark the booking complete");
  guide.observe(response(7, () => {}));
  assert.equal(guide.step, 7);
  assert.equal(nodes.title.textContent, "Booked. Receipt verified.");
});

test("repeated responses, prose and missing evidence cannot advance", () => {
  const first = response(1, () => {});
  guide.observe(first); guide.observe(first);
  assert.equal(guide.step, 1);
  guide.observe(response(2, (r) => { delete r.task.facts.demo_observation; r.response.display_text = "P2 is ready at 15:30."; }));
  assert.equal(guide.step, 1);
  assert.match(nodes.notice.textContent, /cannot verify/);
});

test("the new intent must replace the first draft and exclude 15:00", () => {
  advanceThrough(1);
  guide.observe(response(2, (r) => { r.task.facts.time_constraint.inclusive = true; }));
  assert.equal(guide.step, 1);
  guide.observe(response(2, (r) => { r.interaction_id = "wrong-draft"; r.task.facts.candidate_id = "P1"; }));
  assert.equal(guide.step, 1);
});

test("inquiry requires a successful appointments read and valid grounding", () => {
  advanceThrough(2);
  guide.observe(response(3, (r) => { r.task.facts.demo_observation.successful_reads = []; }));
  assert.equal(guide.step, 2);
  guide.observe(response(3, (r) => { r.interaction_id = "bad-snapshot"; r.task.facts.appointments_snapshot.records = null; }));
  assert.equal(guide.step, 2);
});

test("another query, clarification or unrelated task cannot count as a clash answer", () => {
  advanceThrough(3);
  guide.observe(response(4, (r) => { r.task.facts.demo_observation.control_action = "query_appointments"; }));
  assert.equal(guide.step, 3);
  guide.observe(response(4, (r) => { r.interaction_id = "clarification"; r.recovery = { reason: "needs_clarification" }; }));
  assert.equal(guide.step, 3);
  guide.observe(response(4, (r) => { r.interaction_id = "other-task"; r.task.task_id = "T2"; }));
  assert.equal(guide.step, 3);
});

test("resuming needs a successful fresh search; a missing or changed candidate blocks", () => {
  advanceThrough(4);
  guide.observe(response(5, (r) => { r.task.facts.demo_observation.successful_reads = []; }));
  assert.equal(guide.step, 4);
  guide.observe(response(5, (r) => { r.interaction_id = "stale"; delete r.task.facts.candidate_id; }));
  assert.equal(guide.step, 4);
  guide.observe(response(5, (r) => { r.interaction_id = "wrong-time"; r.task.facts.selected_slot.start = "2026-10-20T16:00:00+08:00"; }));
  assert.equal(guide.step, 4);
});

test("selection requires a formal server-issued approval action", () => {
  advanceThrough(5);
  guide.observe(response(6, (r) => { r.workspace.actions = []; }));
  assert.equal(guide.step, 5);
});

test("unknown outcomes, wrong receipts and ambiguous agreement never complete", () => {
  advanceThrough(6);
  guide.observe(response(7, (r) => { r.receipt = null; r.task.status = "awaiting_input"; }));
  assert.equal(guide.step, 6);
  guide.observe(response(7, (r) => { r.interaction_id = "unknown"; r.recovery = { reason: "outcome_needs_checking" }; }));
  assert.equal(guide.step, 6);
  for (const [key, value] of [["task_id", "OTHER"], ["status", "pending"]]) {
    guide.observe(response(7, (r) => { r.interaction_id = key; r.receipt[key] = value; }));
    assert.equal(guide.step, 6);
  }
  guide.observe(response(7, (r) => { r.interaction_id = "wrong-booking"; r.receipt.appointment.slot_id = "other-slot"; }));
  assert.equal(guide.step, 6);
});

test("busy, reset, exit and disconnected modes keep the guide honest", () => {
  guide.setBusy(true); nodes.use.click(); nodes.exit.click();
  assert.equal(previews.length, 0); assert.equal(guide.active, true);
  guide.setBusy(false); guide.setConnection(false, "real"); nodes.use.click();
  assert.equal(previews.length, 0); assert.match(nodes.notice.textContent, /Connect/);
  guide.setConnection(true, "scripted");
  assert.equal(nodes.mode.textContent, "Guided demo · Scripted");
  advanceThrough(2); guide.reset(); assert.equal(guide.step, 0);
  nodes.exit.click(); assert.equal(guide.active, false); assert.equal(exits, 1);
  guide.observe(response(1, () => {})); assert.equal(guide.step, 0);
});


test("expired drafts can refresh to P3 only with the same intent and a successful slot recheck", () => {
  advanceThrough(4);
  guide.observe(response(5, (r) => { r.task.facts.candidate_id = "P3"; }));
  assert.equal(guide.step, 5);
  guide.observe(response(6, (r) => { r.task.facts.candidate_id = "P4"; }));
  assert.equal(guide.step, 6, "selection may also refresh an expired draft before issuing the card");
});

test("a refreshed proposal cannot silently change the intent or slot", () => {
  advanceThrough(4);
  guide.observe(response(5, (r) => { r.task.facts.candidate_id = "P3"; r.task.facts.intent_revision = 3; }));
  assert.equal(guide.step, 4);
  guide.observe(response(5, (r) => { r.interaction_id = "changed-slot"; r.task.facts.candidate_id = "P3"; r.task.facts.slot_id = "other-1530"; }));
  assert.equal(guide.step, 4);
});
