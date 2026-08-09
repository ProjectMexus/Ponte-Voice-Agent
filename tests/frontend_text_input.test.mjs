import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { startPonteApp } from "../frontend/app.js";

// Browser boundaries stay small: the app, transport, and response delivery run
// unchanged; fetch supplies controlled HTTP responses without paid services.
class TestElement extends EventTarget {
  constructor() {
    super();
    this.dataset = {};
    this.style = {};
    this.children = [];
    this.value = "";
    this.disabled = false;
    this.hidden = true;
    this.attributes = {};
    const classes = new Set();
    this.classList = {
      add: (...names) => names.forEach((name) => classes.add(name)),
      remove: (...names) => names.forEach((name) => classes.delete(name)),
      contains: (name) => classes.has(name),
      toggle: (name, enabled) => enabled ? classes.add(name) : classes.delete(name),
    };
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  querySelector() { return null; }
  querySelectorAll() { return []; }
  closest() { return null; }
  replaceChildren() { this.children = []; }
  append(...children) { this.children.push(...children); }
}

const html = await readFile(new URL("../frontend/index.html", import.meta.url), "utf8");
const ids = [...html.matchAll(/\bid="([^"]+)"/g)].map((match) => match[1]);
const realSetTimeout = globalThis.setTimeout;
globalThis.setTimeout = (...args) => realSetTimeout(...args).unref();

function setup(requestHandler) {
  const elements = new Map(ids.map((id) => [id, new TestElement()]));
  const document = new TestElement();
  document.body = new TestElement();
  document.documentElement = new TestElement();
  document.getElementById = (id) => elements.get(id) || null;
  const localeButtons = ["zh-Hant", "en"].map((locale) => {
    const button = new TestElement();
    button.dataset.locale = locale;
    elements.set(`locale:${locale}`, button);
    return button;
  });
  document.querySelectorAll = (selector) => selector === "[data-locale]" ? localeButtons : [];
  globalThis.document = document;
  globalThis.window = { location: { search: "", origin: "http://localhost" } };
  globalThis.fetch = async (url, options) => {
    if (url === "/api/health") return Response.json({ backend_reachable: true, voice_ready: false });
    return requestHandler(url, options);
  };
  startPonteApp();
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
  const input = elements.get("text-transcript");
  const form = elements.get("text-input-form");
  const submit = elements.get("text-submit");
  assert.ok(form && input && submit, "a text fallback is present in the voice screen");
  input.value = "  我想查詢自己的醫療預約  ";
  input.dispatchEvent(new Event("input"));
  const event = new Event("submit", { cancelable: true });
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
  form.dispatchEvent(new Event("submit", { cancelable: true }));
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
  const input = elements.get("text-transcript");
  const form = elements.get("text-input-form");
  assert.ok(form && input);
  input.value = "   ";
  form.dispatchEvent(new Event("submit", { cancelable: true }));
  assert.equal(requests.length, 0);
  input.value = "Find my appointment";
  input.dispatchEvent(new Event("input"));
  form.dispatchEvent(new Event("submit", { cancelable: true }));
  await settle();
  assert.equal(requests.length, 1);
  assert.equal(input.value, "Find my appointment");
  assert.equal(input.disabled, false);
  assert.equal(elements.get("text-submit").disabled, false);
  assert.equal(elements.get("global-error").textContent, "Try again");
});

test("display language updates the accessible text input controls", () => {
  const elements = setup(() => { throw new Error("No interaction expected"); });
  const initialLabel = elements.get("text-input-label").textContent;
  const initialPlaceholder = elements.get("text-transcript").placeholder;
  elements.get("locale:en").dispatchEvent(new Event("click"));
  assert.equal(document.documentElement.lang, "en");
  assert.notEqual(elements.get("text-input-label").textContent, initialLabel);
  assert.notEqual(elements.get("text-transcript").placeholder, initialPlaceholder);
  assert.equal(elements.get("text-submit").textContent, "Send");
  elements.get("locale:zh-Hant").dispatchEvent(new Event("click"));
  assert.equal(elements.get("text-input-label").textContent, initialLabel);
  assert.equal(elements.get("text-transcript").placeholder, initialPlaceholder);
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
    elements.get("ponte-button").dispatchEvent(new Event("click"));
    assert.equal(elements.get("text-transcript").disabled, true);
    recognition.onend();
    assert.equal(elements.get("text-transcript").disabled, false);
  } finally {
    delete globalThis.SpeechRecognition;
  }
});
