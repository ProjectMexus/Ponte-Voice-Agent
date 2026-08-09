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
  add("section", "activity-panel").hidden = true;
  add("ol", "activity-log", nodes["activity-panel"]);
  add("section", "service-workspace");
  add("h2", "workspace-heading", nodes["service-workspace"]);
  add("span", "task-status", nodes["service-workspace"]);
  add("div", "workspace-loading");
  add("div", "approval-region");
  add("button", "server-action", nodes["approval-region"]);
  add("button", "new-session");
  add("button", "speech-toggle");
  add("span", "sound-label", nodes["speech-toggle"]).setAttribute("data-copy", "soundOn");
  add("button", "medical-scenario").setAttribute("data-prompt", "我想預約醫療服務");
  nodes["medical-scenario"].className = "request-suggestion";
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

test("composer feedback follows text, exact shortcut selection, busy state and reset", () => {
  const input = nodes["message-input"];
  const form = nodes["message-form"];
  const send = nodes["send-button"];
  const suggestion = nodes["medical-scenario"];
  assert.equal(send.disabled, true);
  assert.equal(form.classList.contains("has-content"), false);
  assert.equal(form.getAttribute("aria-busy"), "false");
  assert.equal(suggestion.getAttribute("aria-pressed"), "false");

  suggestion.click();
  assert.equal(form.classList.contains("has-content"), true);
  assert.equal(send.disabled, false);
  assert.equal(suggestion.classList.contains("is-selected"), true);
  assert.equal(suggestion.getAttribute("aria-pressed"), "true");

  input.value += "明天下午";
  input.dispatchEvent(createEvent("input"));
  assert.equal(suggestion.classList.contains("is-selected"), false);
  assert.equal(suggestion.getAttribute("aria-pressed"), "false");
  assert.equal(send.disabled, false);

  ui.preview(" 我想預約醫療服務 ");
  assert.equal(suggestion.getAttribute("aria-pressed"), "false");
  ui.setBusy(true);
  assert.equal(send.disabled, true);
  assert.equal(form.getAttribute("aria-busy"), "true");
  ui.setBusy(false);
  assert.equal(send.disabled, false);
  assert.equal(form.getAttribute("aria-busy"), "false");

  input.value = " \n ";
  input.dispatchEvent(createEvent("input"));
  assert.equal(send.disabled, true);
  assert.equal(form.classList.contains("has-content"), false);
  ui.setBusy(true);
  ui.setBusy(false);
  assert.equal(send.disabled, true);

  ui.preview("我想預約醫療服務");
  ui.reset();
  assert.equal(send.disabled, true);
  assert.equal(form.classList.contains("has-content"), false);
  assert.equal(form.getAttribute("aria-busy"), "false");
  assert.equal(suggestion.classList.contains("is-selected"), false);
  assert.equal(suggestion.getAttribute("aria-pressed"), "false");
  assert.deepEqual(submissions, []);
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
  assert.equal(nodes["activity-panel"].hidden, false);
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
  assert.equal(nodes["activity-panel"].hidden, true);
  assert.equal(nodes["activity-log"].children.length, 0);
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

test("cancellation updates the actual task without forecasting medical phases", () => {
  ui.updateWorkspace({
    task: { task_id: "TASK-1", status: "awaiting_input" },
    workspace: { view: "slot_selection", title: "選擇預約時段", fields: [], actions: [] },
  });
  assert.equal(nodes["workspace-heading"].textContent, "選擇預約時段");
  ui.updateWorkspace({
    task: { task_id: "TASK-1", status: "cancelled" },
    workspace: { view: "slot_selection", title: "選擇預約時段", fields: [], actions: [] },
  });
  assert.equal(nodes["task-status"].textContent, "已取消");
});

test("a completed cash query shows its own service title and keeps the dialogue", () => {
  ui.appendMessage("user", "我想查現金分享計劃");
  ui.appendMessage("assistant", "我已查到現金分享計劃資料。");
  ui.updateWorkspace({
    task: { task_id: "TASK-CASH", type: "cash_sharing_query", status: "completed" },
    workspace: { view: "cash_sharing_summary", title: "現金分享計劃", fields: [], actions: [], artifact: null },
    receipt: null,
  });
  assert.ok(nodes["conversation-log"].textContent.includes("我想查現金分享計劃"));
  assert.ok(nodes["conversation-log"].textContent.includes("我已查到現金分享計劃資料。"));
});

test("conversation suggestions preserve the active task and wait for an explicit send", () => {
  ui.updateWorkspace({
    task: { task_id: "TASK-1", status: "awaiting_confirmation" },
    workspace: { view: "appointment_confirmation", title: "確認預約", fields: [], actions: [] },
  });
  nodes["message-input"].value = "Keep this draft";
  nodes["medical-scenario"].click();
  assert.deepEqual(resetPrompts, []);
  assert.equal(nodes["message-input"].value, "我想預約醫療服務");
  assert.equal(fixture.document.activeElement, nodes["message-input"]);
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


test("conversation and pending requests do not invent service activity", () => {
  assert.equal(nodes["activity-panel"].hidden, true);
  ui.appendMessage("assistant", "你好，有甚麼可以幫你？");
  ui.setBusy(true);
  assert.equal(nodes["activity-panel"].hidden, true);
  ui.setBusy(false);
  ui.updateWorkspace({ response: { display_text: "可以告訴我多一點嗎？" } });
  assert.equal(nodes["activity-panel"].hidden, true);
  assert.equal(nodes["activity-log"].children.length, 0);
});

test("omitted workspace preserves the current task and explicit clearing removes its title", () => {
  ui.updateWorkspace({ task: { task_id: "TASK-1", status: "awaiting_input" }, workspace: { view: "service_selection", title: "選擇醫療服務" } });
  ui.updateWorkspace({ response: { display_text: "請繼續" } });
  assert.equal(nodes["workspace-heading"].textContent, "選擇醫療服務");
  ui.updateWorkspace({ workspace: null });
  assert.equal(nodes["workspace-heading"].textContent, "");
  assert.equal(nodes["task-status"].hidden, true);
  assert.equal(nodes["activity-panel"].hidden, false);
});


test("recovery-only responses replace stale workspace metadata", () => {
  ui.updateWorkspace({ workspace: { view: "slot_selection", title: "OLD SLOT TITLE" } });
  ui.updateWorkspace({ recovery: { reason: "請補充資料" } });
  assert.equal(nodes["workspace-heading"].textContent, "請補充資料");
  assert.equal(nodes["task-status"].textContent, "請補充資料");
});


test("agent service events preserve details without duplicates or fabricated steps", () => {
  const payload = {task:{task_id:"TASK-AGENT"},workspace:{title:"草稿",view:"appointment_draft",activity:[
    {id:"E1",title:"查詢可用時段",detail:"已收到服務回覆。",at:"2026-10-14T10:00:00+08:00",status:"completed"},
    {id:"E2",title:"需要你澄清",detail:"<img src=x> 請指定時間",at:"2026-10-14T10:01:00+08:00",status:"attention"}
  ]}};
  ui.updateWorkspace(payload);
  ui.updateWorkspace(payload);
  assert.equal(nodes["activity-log"].children.length,2);
  assert.match(nodes["activity-log"].textContent,/請指定時間/);
  assert.equal(nodes["activity-log"].querySelector("img"),null);
  assert.equal(nodes["activity-log"].children[1].dataset.status,"attention");
  ui.reset();
  ui.updateWorkspace(payload);
  assert.equal(nodes["activity-log"].children.length,2);
});


test("one task status follows processing, confirmation and recovery without repeating the title", () => {
  ui.setBusy(true);
  assert.equal(nodes["task-status"].dataset.status,"running");
  assert.equal(nodes["task-status"].textContent,"正在處理");
  ui.updateWorkspace({task:{status:"awaiting_confirmation"},workspace:{title:"確認掛號"}});
  ui.setBusy(false);
  assert.equal(nodes["task-status"].textContent,"待確認");
  ui.setLocale("en");
  assert.equal(nodes["task-status"].textContent,"Awaiting confirmation");
  ui.setLocale("zh-Hant");
  ui.updateWorkspace({workspace:null,recovery:{message:"請補充資料"}});
  assert.equal(nodes["workspace-heading"].textContent,"請補充資料");
  assert.equal(nodes["task-status"].hidden,true);
  ui.reset();
  assert.equal(nodes["task-status"].hidden,true);
});


test("English quick requests send English while language changes preserve custom text", () => {
  ui.setLocale("en");
  nodes["medical-scenario"].click();
  assert.equal(nodes["message-input"].value,"I would like to book a medical appointment.");
  assert.equal(nodes["medical-scenario"].getAttribute("aria-pressed"),"true");
  ui.setLocale("zh-Hant");
  assert.equal(nodes["message-input"].value,"我想預約醫療服務");
  nodes["message-input"].value="My own request";
  ui.setLocale("en");
  assert.equal(nodes["message-input"].value,"My own request");
});
