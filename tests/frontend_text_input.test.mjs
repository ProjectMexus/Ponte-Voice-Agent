import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { createDOM, createEvent } from "./helpers/dom-fixture.mjs";
import { startPonteApp } from "../frontend/app.js";

// Browser boundaries stay small: the app, transport, and response delivery run
// unchanged; fetch supplies controlled HTTP responses without paid services.
const html = await readFile(new URL("../frontend/index.html", import.meta.url), "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const realSetTimeout = globalThis.setTimeout;
globalThis.setTimeout = (...args) => realSetTimeout(...args).unref();

function setup(requestHandler, { guided = false, demoMode = "off" } = {}) {
  const fixture = createDOM();
  const document = fixture.document;
  const elements = new Map();
  for (const match of html.matchAll(/<([a-z][a-z0-9-]*)\b[^>]*\bid="([^"]+)"[^>]*>/g)) {
    const node = fixture.add(match[1], match[2]);
    node.style = {};
    for (const attr of match[0].matchAll(/(data-[\w-]+|aria-[\w-]+)="([^"]*)"/g)) node.setAttribute(attr[1], attr[2]);
    node.hidden = /\shidden(?:\s|>)/.test(match[0]);
    elements.set(match[2], node);
  }
  elements.get("message-form").append(elements.get("message-input"), elements.get("send-button"));
  elements.get("conversation-log").append(elements.get("conversation-empty"));
  elements.get("activity-panel").append(elements.get("activity-log"));
  const inputLabel = fixture.add("label", "message-input-label");
  inputLabel.setAttribute("data-copy", "inputLabel");
  elements.set("message-input-label", inputLabel);
  const sendLabel = fixture.add("span", "", elements.get("send-button"));
  sendLabel.setAttribute("data-copy", "send");
  const soundLabel = fixture.add("span", "", elements.get("speech-toggle"));
  soundLabel.setAttribute("data-copy", "soundOn");
  for (const locale of ["zh-Hant", "en"]) {
    const button = fixture.add("button");
    button.setAttribute("data-locale", locale);
    elements.set(`locale:${locale}`, button);
  }
  globalThis.document = document;
  globalThis.window = { location: { search: guided ? "?guide=medical" : "", origin: "http://localhost" } };
  elements.get("reset-dialog").showModal = () => { elements.get("reset-dialog").open = true; };
  elements.get("reset-dialog").close = () => { elements.get("reset-dialog").open = false; };
  globalThis.fetch = async (url, options) => {
    if (url === "/api/health") return Response.json({ backend_reachable: true, voice_ready: false, demo_agent_mode: demoMode });
    return requestHandler(url, options);
  };
  elements.app = startPonteApp();
  return elements;
}

const settle = () => new Promise(setImmediate);

test("keyboard text submits a trimmed canonical utterance and prevents duplicates", async () => {
  const requests = [];
  let release;
  const elements = setup((url, options) => {
    requests.push({ url, body: JSON.parse(options.body) });
    return new Promise((resolve) => { release = resolve; });
  });
  const input = elements.get("message-input");
  const form = elements.get("message-form");
  const submit = elements.get("send-button");
  assert.ok(form && input && submit, "a text fallback is present in the voice screen");
  input.value = "  我想查詢自己的醫療預約  ";
  input.dispatchEvent(createEvent("input"));
  const event = createEvent("submit");
  form.dispatchEvent(event);
  assert.equal(event.defaultPrevented, true);
  assert.equal(requests.length, 1);
  assert.equal(requests[0].url, "/api/interactions");
  assert.deepEqual(requests[0].body.event, {
    type: "user_utterance", task_id: null, content: "我想查詢自己的醫療預約",
  });
  assert.match(requests[0].body.routing.interaction_id, /^INT-/);
  assert.match(requests[0].body.routing.session_id, /^S-/);
  assert.equal(input.disabled, true);
  assert.equal(submit.disabled, true);
  form.dispatchEvent(createEvent("submit"));
  assert.equal(requests.length, 1, "processing cannot send the same form twice");
  release(Response.json({ response: { display_text: "查詢完成", speech_text: "" } }));
  await settle();
  assert.equal(input.disabled, false, "text remains usable without browser audio");
  assert.equal(input.value, "", "accepted input clears after delivery");
  assert.equal(submit.disabled, true, "an empty input cannot be submitted");
  assert.equal(elements.get("caption-line").textContent, "小澳：查詢完成");
});

test("empty text is ignored and failed requests retain input for retry", async () => {
  const requests = [];
  const elements = setup((url, options) => {
    requests.push({ url, body: JSON.parse(options.body) });
    return Response.json({ error: { code: "UNAVAILABLE", message: "Try again" } }, { status: 503 });
  });
  const input = elements.get("message-input");
  const form = elements.get("message-form");
  assert.ok(form && input);
  input.value = "   ";
  form.dispatchEvent(createEvent("submit"));
  assert.equal(requests.length, 0);
  input.value = "Find my appointment";
  input.dispatchEvent(createEvent("input"));
  form.dispatchEvent(createEvent("submit"));
  await settle();
  assert.equal(requests.length, 1);
  assert.equal(input.value, "Find my appointment");
  assert.equal(input.disabled, false);
  assert.equal(elements.get("send-button").disabled, false);
  assert.ok(elements.get("global-error").textContent.includes("Try again"));
});

test("display language updates the accessible text input controls", () => {
  const elements = setup(() => { throw new Error("No interaction expected"); });
  const initialLabel = elements.get("message-input-label").textContent;
  const initialPlaceholder = elements.get("message-input").placeholder;
  elements.get("locale:en").dispatchEvent(createEvent("click"));
  assert.equal(document.documentElement.lang, "en");
  assert.notEqual(elements.get("message-input-label").textContent, initialLabel);
  assert.notEqual(elements.get("message-input").placeholder, initialPlaceholder);
  assert.equal(elements.get("send-button").textContent, "Send");
  elements.get("locale:zh-Hant").dispatchEvent(createEvent("click"));
  assert.equal(elements.get("message-input-label").textContent, initialLabel);
  assert.equal(elements.get("message-input").placeholder, initialPlaceholder);
});

test("ending browser recognition without a transcript restores the text fallback", async () => {
  let recognition;
  globalThis.SpeechRecognition = class {
    constructor() { recognition = this; }
    start() { this.onstart(); }
    stop() { this.onend(); }
  };
  try {
    const elements = setup(() => { throw new Error("No interaction expected"); });
    await settle();
    elements.get("ponte-button").dispatchEvent(createEvent("click"));
    assert.equal(elements.get("message-input").disabled, true);
    recognition.onend();
    assert.equal(elements.get("message-input").disabled, false);
  } finally {
    delete globalThis.SpeechRecognition;
  }
});


test("English input carries a language preference outside the authoritative event", async () => {
  const requests=[];
  const elements=setup((url, options) => {
    requests.push(JSON.parse(options.body));
    return Response.json({response:{display_text:"Choose a service.",speech_text:""}});
  });
  elements.get("locale:en").dispatchEvent(createEvent("click"));
  elements.get("message-input").value="Book a medical appointment";
  elements.get("message-input").dispatchEvent(createEvent("input"));
  elements.get("message-form").dispatchEvent(createEvent("submit"));
  await settle();
  assert.equal(requests[0].audit.locale,"en");
  assert.deepEqual(requests[0].event,{type:"user_utterance",task_id:null,content:"Book a medical appointment"});
});


test("guided URL starts English, previews without sending, and holds progress on HTTP errors", async () => {
  const requests = [];
  let release;
  const elements = setup((url, options) => {
    requests.push(JSON.parse(options.body));
    return new Promise((resolve) => { release = resolve; });
  }, { guided: true, demoMode: "real" });
  await settle();
  assert.equal(document.documentElement.lang, "en");
  assert.equal(elements.get("language-toggle").hidden, true);
  assert.equal(elements.get("guided-demo").hidden, false);
  assert.equal(elements.get("guide-mode").textContent, "Guided demo · Live LLM");
  elements.get("locale:zh-Hant").click();
  assert.equal(document.documentElement.lang, "en", "guided messages stay English");
  elements.get("guide-use").click();
  assert.equal(elements.get("message-input").value, "Book a cardiology appointment next Tuesday afternoon");
  assert.equal(requests.length, 0);
  elements.get("message-form").dispatchEvent(createEvent("submit"));
  assert.equal(requests[0].audit.locale, "en");
  assert.equal(elements.get("guide-use").disabled, true);
  elements.get("guide-use").click();
  assert.equal(requests.length, 1);
  release(Response.json({ error: { code: "UNAVAILABLE", message: "Try again" } }, { status: 503 }));
  await settle();
  assert.equal(elements.app.guidedDemo.step, 0);
  assert.match(elements.get("guide-notice").textContent, /did not finish/);
  assert.equal(elements.get("guide-use").disabled, false);
  elements.get("guide-exit").click();
  assert.equal(elements.get("guided-demo").hidden, true);
  assert.equal(elements.get("language-toggle").hidden, false);
  assert.equal(elements.get("conversation-log").children.length, 1, "exit preserves conversation");
});

test("starting the guide from a conversation waits for reset approval; cancel and Escape preserve it", async () => {
  const elements = setup(() => Response.json({ response: { display_text: "Which service?", speech_text: "" } }), { demoMode: "scripted" });
  elements.get("message-input").value = "Hello";
  elements.get("message-form").dispatchEvent(createEvent("submit"));
  await settle();
  const oldSession = elements.app.sessionId;
  elements.get("guide-start").click();
  assert.equal(elements.get("reset-dialog").open, true);
  assert.equal(elements.app.guidedDemo.active, false);
  elements.get("reset-cancel").click();
  assert.equal(elements.app.sessionId, oldSession);
  elements.get("guide-start").click();
  elements.get("reset-dialog").dispatchEvent(createEvent("cancel"));
  elements.get("reset-dialog").close();
  elements.get("new-session").click();
  elements.get("reset-confirm").click();
  assert.equal(elements.app.guidedDemo.active, false, "Escape clears the pending guide start");
  elements.get("guide-start").click();
  assert.equal(elements.app.guidedDemo.active, true);
  assert.equal(document.documentElement.lang, "en");
  elements.get("new-session").click(); elements.get("reset-confirm").click();
  assert.equal(elements.app.guidedDemo.step, 0, "reset keeps an active guide at step one");
});
