import assert from "node:assert/strict";
import test from "node:test";
import { createDOM, createEvent } from "./helpers/dom-fixture.mjs";
import { renderWorkspace } from "../frontend/interaction-view.js";
import { createVoiceExceptions } from "../frontend/voice-exceptions.js";

function setup(onAction) {
  const { document, add } = createDOM();
  globalThis.document = document;
  globalThis.window = { print() {} };
  const surface = add("section", "voice-exceptions", document.body, "voice-exceptions");
  const errorRoot = add("div", "global-error", surface);
  errorRoot.hidden = true;
  const workspaceSurface = add("section", "service-workspace", surface);
  workspaceSurface.hidden = true;
  const heading = add("h2", "workspace-heading", workspaceSurface);
  heading.tabIndex = -1;
  const approvalRoot = add("div", "approval-region", workspaceSurface);
  const artifactRoot = add("aside", "artifact-drawer");
  artifactRoot.hidden = true;
  const backdrop = add("div", "", artifactRoot);
  backdrop.setAttribute("data-artifact-close", "");
  const print = add("button", "artifact-print", artifactRoot);
  const download = add("button", "artifact-download", artifactRoot);
  const close = add("button", "", artifactRoot);
  close.setAttribute("data-artifact-close", "");
  const artifactContentRoot = add("div", "artifact-content", artifactRoot);
  const view = createVoiceExceptions({ approvalRoot, errorRoot, artifactRoot, artifactContentRoot, onAction });
  return { document, add, surface, workspaceSurface, errorRoot, approvalRoot, artifactRoot, artifactContentRoot, print, download, close, view };
}

const readonlyWorkspace = {
  view: "appointment_list", title: "我的預約",
  fields: [{ key: "appointment_0", label: "腹部超聲波檢查", value: "2026-10-15 · 15:00 · 景湖醫療中心 · confirmed" }],
  actions: [], artifact: null,
};

const receipt = {
  receipt_id: "MED-1", kind: "medical_appointment", status: "completed", issued_at: "2026-10-13T08:00:00Z", task_id: "TASK-1",
  appointment: { service: "腹部超聲波檢查", date: "2026-10-15", time: "15:00", location: "景湖醫療中心", status: "confirmed" },
};

test("read-only service results remain available after time and unrelated conversation", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { approvalRoot, view, document, surface } = setup();
  view.renderResponse({ workspace: readonlyWorkspace });
  t.mock.timers.tick(15_000);
  assert.match(approvalRoot.textContent, /景湖醫療中心/);
  view.renderResponse({ response: { display_text: "還有甚麼可以幫你？" } });
  assert.match(approvalRoot.textContent, /腹部超聲波檢查/);
  document.dispatchEvent(createEvent("keydown", { key: "Escape" }));
  surface.dispatchEvent(createEvent("pointerdown", { target: surface }));
  t.mock.timers.tick(500);
  assert.match(approvalRoot.textContent, /景湖醫療中心/);
  assert.equal(surface.classList.contains("has-modal"), false);
});

test("server options preserve exact issued events and avoid duplicate option buttons", () => {
  const selected = [];
  const { approvalRoot, document, view, add } = setup((event) => selected.push(event));
  const composer = add("input", "message-input");
  composer.focus();
  const event = { type: "service_selected", action_id: "ACT-TASK-1-SVC-0", task_id: "TASK-1", service_id: "SERVICE-1", date_from: "2026-10-13", date_to: "2026-10-27" };
  const field = { key: "service_0", label: "腹部超聲波檢查", value: "30 分鐘", action: { event } };
  view.renderResponse({ workspace: { view: "service_selection", title: "選擇服務", fields: [field], actions: [{ label: "選擇服務", event }], artifact: null } });
  const buttons = approvalRoot.querySelectorAll("button");
  assert.equal(buttons.length, 1);
  assert.equal(buttons[0].closest("dl"), null);
  assert.equal(buttons[0].closest(".workspace-options")?.getAttribute("role"), "group");
  assert.match(buttons[0].textContent, /腹部超聲波檢查/);
  assert.match(buttons[0].textContent, /30 分鐘/);
  buttons[0].click();
  assert.equal(selected[0], event);
  assert.equal(document.activeElement, composer);
});

test("independent actions without identifiers are retained", () => {
  const { approvalRoot } = setup();
  renderWorkspace(approvalRoot, {
    title: "Choose", fields: [{ label: "Option", value: "A", action: { event: { type: "custom", value: "A" } } }],
    actions: [{ label: "Other", event: { type: "custom", value: "B" } }],
  });
  assert.equal(approvalRoot.querySelectorAll("button").length, 2);
});

test("explicitly cleared workspace removes outdated canonical actions", () => {
  const { approvalRoot, view } = setup();
  view.renderResponse({ workspace: readonlyWorkspace });
  view.renderResponse({ workspace: null });
  assert.equal(approvalRoot.children.length, 0);
});

test("service errors stay visible until dismissed or a successful response", (t) => {
  t.mock.timers.enable({ apis: ["setTimeout"] });
  const { errorRoot, view } = setup();
  view.renderError(new Error("Cannot connect"));
  t.mock.timers.tick(15_000);
  assert.equal(errorRoot.hidden, false);
  assert.match(errorRoot.textContent, /Cannot connect/);
  const dismiss = errorRoot.querySelector("button");
  assert.ok(dismiss);
  dismiss.click();
  assert.equal(errorRoot.hidden, true);
  view.renderError(new Error("Cannot connect"));
  view.renderResponse({ workspace: readonlyWorkspace });
  assert.equal(errorRoot.hidden, true);
});

test("receipt facts and reference remain visible and receipt drawer restores focus", () => {
  const { approvalRoot, artifactRoot, artifactContentRoot, document, close, view } = setup();
  view.renderResponse({ workspace: readonlyWorkspace, receipt });
  const receiptCard = approvalRoot.querySelector(".receipt-card");
  assert.equal(receiptCard.querySelector(".voice-facts"), null);
  assert.match(receiptCard.textContent, /MED-1/);
  const open = receiptCard.querySelector("button");
  open.focus();
  open.click();
  assert.equal(artifactRoot.hidden, false);
  assert.match(artifactContentRoot.textContent, /2026-10-15/);
  assert.equal(document.activeElement, close);
  close.click();
  assert.equal(artifactRoot.hidden, true);
  assert.equal(document.activeElement, open);
});

test("receipt dialog traps keyboard focus and Escape closes only the dialog", () => {
  const { approvalRoot, artifactRoot, document, print, close, view } = setup();
  view.renderResponse({ workspace: readonlyWorkspace, receipt });
  view.openArtifact();
  close.focus();
  const forward = createEvent("keydown", { key: "Tab", shiftKey: false });
  document.dispatchEvent(forward);
  assert.equal(document.activeElement, print);
  assert.equal(forward.defaultPrevented, true);
  const reverse = createEvent("keydown", { key: "Tab", shiftKey: true });
  document.dispatchEvent(reverse);
  assert.equal(document.activeElement, close);
  document.dispatchEvent(createEvent("keydown", { key: "Escape" }));
  assert.equal(artifactRoot.hidden, true);
  assert.match(approvalRoot.textContent, /腹部超聲波檢查/);
});

test("reset removes the old session workspace, receipt and error", () => {
  const { approvalRoot, artifactRoot, errorRoot, view } = setup();
  view.renderResponse({ workspace: readonlyWorkspace, receipt });
  view.renderError(new Error("Failed"));
  view.openArtifact();
  view.reset();
  assert.equal(approvalRoot.children.length, 0);
  assert.equal(errorRoot.hidden, true);
  assert.equal(artifactRoot.hidden, true);
  view.openArtifact();
  assert.equal(artifactRoot.hidden, true);
});

test("English display localizes labels without changing canonical values", () => {
  const { approvalRoot, document, view } = setup();
  document.documentElement.lang = "en";
  view.renderResponse({ workspace: readonlyWorkspace, receipt });
  assert.equal(approvalRoot.querySelector(".workspace-section-label"),null);
  assert.ok(approvalRoot.querySelector("dl"));
  assert.match(approvalRoot.textContent, /View receipt/);
  assert.match(approvalRoot.textContent, /景湖醫療中心/);
  assert.doesNotMatch(approvalRoot.textContent, /appointment_list/);
});


test("workspace opens only for agent content, preserves omitted projections, and hides when cleared", () => {
  const { workspaceSurface, view } = setup();
  assert.equal(workspaceSurface.hidden, true);
  view.renderResponse({ response: { display_text: "你好" } });
  assert.equal(workspaceSurface.hidden, true);
  view.renderResponse({ workspace: readonlyWorkspace });
  assert.equal(workspaceSurface.hidden, false);
  view.renderResponse({ response: { display_text: "請繼續" } });
  assert.equal(workspaceSurface.hidden, false);
  view.renderResponse({ workspace: null });
  assert.equal(workspaceSurface.hidden, true);
});

test("errors stay visible without opening an empty workspace", () => {
  const { workspaceSurface, errorRoot, view } = setup();
  view.renderError(new Error("Cannot connect"));
  assert.equal(errorRoot.hidden, false);
  assert.equal(workspaceSurface.hidden, true);
  view.clearError();
  assert.equal(workspaceSurface.hidden, true);
});

test("agent recovery and receipt-only responses can open the workspace, and reset hides it", () => {
  const { workspaceSurface, view } = setup();
  view.renderResponse({ recovery: { reason: "請補充服務資料" } });
  assert.equal(workspaceSurface.hidden, false);
  view.reset();
  assert.equal(workspaceSurface.hidden, true);
  view.renderResponse({ receipt });
  assert.equal(workspaceSurface.hidden, false);
  view.reset();
  assert.equal(workspaceSurface.hidden, true);
});


test("embedded workspace uses the outer service title once and preserves option actions", () => {
  const { approvalRoot, view } = setup();
  view.renderResponse({workspace:readonlyWorkspace});
  assert.equal(approvalRoot.querySelector(".workspace-title"),null);
  assert.equal(approvalRoot.querySelector(".workspace-kicker"),null);
  assert.equal(approvalRoot.querySelector(".workspace-card").getAttribute("aria-labelledby"),"workspace-heading");
  approvalRoot.replaceChildren();
  renderWorkspace(approvalRoot,readonlyWorkspace);
  assert.equal(approvalRoot.querySelector(".workspace-title").textContent,"我的預約");
});

test("receipt control replaces the duplicate receipt card and supports receipt-only responses", () => {
  const { document, add, approvalRoot, artifactRoot, view } = setup();
  const control=add("button","last-receipt");
  control.hidden=true;
  view.renderResponse({workspace:readonlyWorkspace,receipt});
  view.renderResponse({workspace:readonlyWorkspace,receipt});
  assert.equal(control.hidden,false);
  assert.equal(approvalRoot.querySelector(".receipt-card"),null);
  assert.equal(approvalRoot.children.length,1);
  view.openArtifact();
  assert.equal(artifactRoot.hidden,false);
  view.reset();
  view.renderResponse({workspace:null,receipt});
  assert.match(approvalRoot.textContent,/MED-1/);
  assert.equal(approvalRoot.querySelector("h2"),null);
});


test("successive receipt-only responses keep the visible reference and opened receipt aligned", () => {
  const { add, approvalRoot, artifactContentRoot, view } = setup();
  add("button","last-receipt");
  view.renderResponse({receipt});
  const next = {...receipt,receipt_id:"MED-2"};
  view.renderResponse({receipt:next});
  assert.match(approvalRoot.textContent,/MED-2/);
  assert.doesNotMatch(approvalRoot.textContent,/MED-1/);
  assert.equal(approvalRoot.querySelectorAll(".receipt-summary").length,1);
  view.openArtifact();
  assert.match(artifactContentRoot.textContent,/MED-2/);
});
