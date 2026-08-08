import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";
import { readFile } from "node:fs/promises";
import { createDOM, createEvent } from "./helpers/dom-fixture.mjs";

const source = await readFile(new URL("../frontend/demo-console.js", import.meta.url), "utf8");
const { createDemoConsole } = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);

let fixture;
let ui;
let nodes;
let submissions;
let resets;
let resetPrompts;
let muteChanges;

beforeEach(() => {
  fixture = createDOM();
  globalThis.document = fixture.document;
  nodes = {};
  const add = (tag, id, parent) => (nodes[id] = fixture.add(tag, id, parent));
  add("form", "message-form");
  add("textarea", "message-input", nodes["message-form"]);
  add("button", "send-button", nodes["message-form"]);
  add("div", "conversation-log");
  add("div", "conversation-empty", nodes["conversation-log"]);
  add("span", "turn-count");
  add("ol", "activity-log");
  add("li", "activity-empty", nodes["activity-log"]);
  add("section", "service-workspace");
  add("h2", "workspace-heading", nodes["service-workspace"]);
  add("span", "task-status", nodes["service-workspace"]);
  add("div", "workspace-empty");
  add("div", "workspace-loading");
  add("ol", "workflow-progress");
  for (let index = 0; index < 4; index += 1) {
    const step = add("li", `step-${index}`, nodes["workflow-progress"]);
    step.setAttribute("data-phase", String(index));
  }
  add("div", "approval-region");
  add("button", "server-action", nodes["approval-region"]);
  add("button", "start-demo");
  add("button", "new-session");
  add("button", "speech-toggle");
  add("span", "sound-label", nodes["speech-toggle"]).setAttribute("data-copy", "soundOn");
  add("button", "medical-scenario").setAttribute("data-prompt", "我想預約醫療服務");
  nodes["medical-scenario"].className = "scenario-card";
  submissions = [];
  resets = 0;
  resetPrompts = [];
  muteChanges = [];
  ui = createDemoConsole({
    onSubmit: (text) => { submissions.push(text); },
    onReset: (prompt) => { resets += 1; resetPrompts.push(prompt); },
    onMute: (muted) => { muteChanges.push(muted); },
  });
});

test("a scenario previews its phrase so a presenter can review before sending", () => {
  nodes["medical-scenario"].click();
  assert.equal(nodes["message-input"].value, "我想預約醫療服務");
  assert.deepEqual(submissions, []);
  assert.equal(fixture.document.activeElement, nodes["message-input"]);
});

test("the composer trims a request and ignores whitespace-only submissions", () => {
  nodes["message-input"].value = "   ";
  const blank = createEvent("submit");
  nodes["message-form"].dispatchEvent(blank);
  assert.equal(blank.defaultPrevented, true);
  assert.deepEqual(submissions, []);
  nodes["message-input"].value = "  我想預約醫療服務 \n";
  nodes["message-form"].dispatchEvent(createEvent("submit"));
  assert.deepEqual(submissions, ["我想預約醫療服務"]);
});

test("a pending request blocks duplicate submission and conflicting workspace actions", () => {
  nodes["message-input"].value = "我想預約醫療服務";
  ui.setBusy(true);
  nodes["message-form"].dispatchEvent(createEvent("submit"));
  nodes["medical-scenario"].click();
  nodes["new-session"].click();
  assert.deepEqual(submissions, []);
  assert.equal(resets, 0);
  assert.equal(nodes["send-button"].disabled, true);
  assert.equal(nodes["server-action"].disabled, true);
  assert.equal(nodes["new-session"].disabled, true);
  assert.ok(nodes["message-input"].disabled || nodes["message-input"].readOnly);
  ui.setBusy(false);
  assert.equal(nodes["send-button"].disabled, false);
  assert.equal(nodes["server-action"].disabled, false);
  nodes["message-form"].dispatchEvent(createEvent("submit"));
  assert.deepEqual(submissions, ["我想預約醫療服務"]);
});

test("conversation messages survive workspace changes and display markup as literal text", () => {
  const literal = '<img src="x" onerror="alert(1)"> 預約';
  ui.appendMessage("user", literal);
  ui.appendMessage("assistant", "請選擇醫療服務。");
  ui.updateWorkspace({
    task: { task_id: "TASK-1", status: "awaiting_input" },
    workspace: { view: "slot_selection", title: "選擇預約時段", fields: [], actions: [] },
  });
  assert.ok(nodes["conversation-log"].textContent.includes(literal));
  assert.ok(nodes["conversation-log"].textContent.includes("請選擇醫療服務。"));
  assert.equal(nodes["conversation-log"].querySelector("img"), null);
  assert.ok(nodes["conversation-empty"].hidden || !nodes["conversation-empty"].isConnected);
});

test("activity shows server workspace titles while excluding raw facts and internal identifiers", () => {
  const response = {
    task: { task_id: "TASK-SECRET-ID", status: "awaiting_input", facts: { token: "SECRET-TOKEN" } },
    workspace: { view: "service_selection", title: "選擇醫療服務", fields: [], actions: [] },
  };
  ui.updateWorkspace(response);
  ui.updateWorkspace(response);
  assert.equal(nodes["workspace-heading"].textContent, "選擇醫療服務");
  assert.ok(nodes["activity-log"].textContent.includes("選擇醫療服務"));
  assert.ok(!nodes["activity-log"].textContent.includes("SECRET-TOKEN"));
  assert.ok(!nodes["activity-log"].textContent.includes("TASK-SECRET-ID"));
  assert.equal(nodes["activity-log"].children.length, 1);
  assert.equal(nodes["workspace-empty"].hidden, true);
});

test("reset clears prior messages, activity and typed content for a new session", () => {
  ui.appendMessage("user", "OLD PRIVATE MESSAGE");
  ui.updateWorkspace({
    task: { task_id: "TASK-1", status: "completed" },
    workspace: { view: "appointment_completed", title: "OLD WORKSPACE TITLE", fields: [], actions: [] },
  });
  nodes["message-input"].value = "OLD DRAFT";
  ui.reset();
  assert.ok(!nodes["conversation-log"].textContent.includes("OLD PRIVATE MESSAGE"));
  assert.ok(!nodes["activity-log"].textContent.includes("OLD WORKSPACE TITLE"));
  assert.ok(!nodes["workspace-heading"].textContent.includes("OLD WORKSPACE TITLE"));
  assert.equal(nodes["message-input"].value, "");
  assert.equal(fixture.document.getElementById("conversation-empty")?.hidden, false);
  assert.equal(nodes["workspace-empty"].hidden, false);
});

test("mute controls notify playback without clearing the conversation", () => {
  ui.appendMessage("assistant", "保留這段對話");
  nodes["speech-toggle"].click();
  assert.equal(ui.muted, true);
  assert.deepEqual(muteChanges, [true]);
  nodes["speech-toggle"].click();
  assert.equal(ui.muted, false);
  assert.deepEqual(muteChanges, [true, false]);
  assert.ok(nodes["conversation-log"].textContent.includes("保留這段對話"));
});

test("cancellation clears active and completed phases despite the previous slot view", () => {
  ui.updateWorkspace({
    task: { task_id: "TASK-1", status: "awaiting_input" },
    workspace: { view: "slot_selection", title: "選擇預約時段", fields: [], actions: [] },
  });
  assert.equal(nodes["step-1"].getAttribute("aria-current"), "step");
  ui.updateWorkspace({
    task: { task_id: "TASK-1", status: "cancelled" },
    workspace: { view: "slot_selection", title: "選擇預約時段", fields: [], actions: [] },
  });
  assert.equal(nodes["workflow-progress"].hidden, true);
  assert.equal(nodes["workflow-progress"].querySelector("[aria-current]"), null);
  assert.equal(nodes["workflow-progress"].querySelector(".is-complete"), null);
  assert.equal(nodes["task-status"].textContent, "已取消");
});

test("a completed cash query hides medical booking phases and keeps the dialogue", () => {
  ui.appendMessage("user", "我想查現金分享計劃");
  ui.appendMessage("assistant", "我已查到現金分享計劃資料。");
  ui.updateWorkspace({
    task: { task_id: "TASK-CASH", type: "cash_sharing_query", status: "completed" },
    workspace: { view: "cash_sharing_summary", title: "現金分享計劃", fields: [], actions: [], artifact: null },
    receipt: null,
  });
  assert.equal(nodes["workflow-progress"].hidden, true);
  assert.equal(nodes["workflow-progress"].querySelector(".is-complete"), null);
  assert.ok(nodes["conversation-log"].textContent.includes("我想查現金分享計劃"));
  assert.ok(nodes["conversation-log"].textContent.includes("我已查到現金分享計劃資料。"));
});

test("changing scenario during an active task requests a new session without replacing the draft", () => {
  ui.updateWorkspace({
    task: { task_id: "TASK-1", status: "awaiting_confirmation" },
    workspace: { view: "appointment_confirmation", title: "確認預約", fields: [], actions: [] },
  });
  nodes["message-input"].value = "Keep this draft";
  nodes["medical-scenario"].click();
  assert.deepEqual(resetPrompts, ["我想預約醫療服務"]);
  assert.equal(nodes["message-input"].value, "Keep this draft");
  assert.deepEqual(submissions, []);
  assert.equal(nodes["workspace-heading"].textContent, "確認預約");
});

test("composing and Shift Enter preserve input while a pending request blocks ordinary Enter", () => {
  nodes["message-input"].value = "我想預約醫療服務";
  const composing = createEvent("keydown", { key: "Enter", isComposing: true });
  nodes["message-input"].dispatchEvent(composing);
  const newline = createEvent("keydown", { key: "Enter", shiftKey: true });
  nodes["message-input"].dispatchEvent(newline);
  assert.equal(composing.defaultPrevented, false);
  assert.equal(newline.defaultPrevented, false);
  assert.deepEqual(submissions, []);
  ui.setBusy(true);
  nodes["message-input"].dispatchEvent(createEvent("keydown", { key: "Enter" }));
  assert.deepEqual(submissions, []);
  ui.setBusy(false);
  const enter = createEvent("keydown", { key: "Enter" });
  nodes["message-input"].dispatchEvent(enter);
  assert.equal(enter.defaultPrevented, true);
  assert.deepEqual(submissions, ["我想預約醫療服務"]);
});
