import assert from "node:assert/strict";
import {beforeEach, test} from "node:test";
import {createSpeechController} from "../frontend/speech.js";

let voices, spoken, states, handlers, timers, speech;
const mandarin = {name:"Mandarin", lang:"zh-CN"};
const cantonese = {name:"Hong Kong voice", lang:"zh-HK"};
beforeEach(() => {
  voices = []; spoken = []; states = []; handlers = new Set(); timers = new Map();
  globalThis.SpeechSynthesisUtterance = class {constructor(text) {this.text = text;}};
  globalThis.speechSynthesis = {
    cancel() {}, resume() {}, getVoices: () => voices,
    speak: utterance => spoken.push(utterance),
    addEventListener: (_type, callback) => handlers.add(callback),
    removeEventListener: (_type, callback) => handlers.delete(callback),
  };
  speech = createSpeechController({onStateChange: state => states.push(state),
    schedule: (callback) => {const id = {}; timers.set(id,callback); return id;},
    unschedule: id => timers.delete(id),
  });
});
function loadVoices(next) {voices = next; [...handlers].forEach(callback => callback());}
function expire() {[...timers.values()].forEach(callback => callback());}

test("selects the Cantonese voice even when Mandarin is the system default", () => {
  voices = [mandarin, cantonese];
  assert.equal(speech.speak("你好，我係小澳。"),true);
  assert.equal(spoken[0].voice,cantonese);
  assert.equal(spoken[0].lang,"zh-HK");
  assert.equal(timers.size,0);
});

test("recognizes Cantonese language tags and explicit Cantonese names", () => {
  for (const voice of [{name:"Yue",lang:"yue-Hant-HK"}, {name:"HK",lang:"zh_HK"}, {name:"Google 粵語",lang:"zh"}]) {
    voices = [mandarin,voice];
    speech.speak("你好");
    assert.equal(spoken.at(-1).voice,voice);
  }
});

test("waits for asynchronous voice enumeration instead of using Mandarin", () => {
  speech.speak("你好");
  assert.equal(spoken.length,0);
  loadVoices([mandarin,cantonese]);
  assert.equal(spoken.length,1);
  assert.equal(spoken[0].voice,cantonese);
  assert.equal(timers.size,0);
  assert.equal(handlers.size,0);
});

test("reports unavailable Cantonese without speaking another language", () => {
  voices = [mandarin,{name:"English",lang:"en-US"}];
  speech.speak("你好");
  expire();
  assert.equal(spoken.length,0);
  assert.equal(states.at(-1),"cantonese-unavailable");
  assert.equal(timers.size,0);
  assert.equal(handlers.size,0);
});

test("mute cancels pending speech and ignores late enumeration", () => {
  speech.speak("舊回覆");
  const stale = [...handlers];
  speech.stopSpeaking();
  loadVoices([cantonese]);
  stale.forEach(callback => callback());
  assert.equal(spoken.length,0);
  assert.equal(timers.size,0);
});

test("a newer reply replaces queued speech and stale callbacks cannot finish it", () => {
  let ended = 0;
  voices = [cantonese];
  speech.speak("舊回覆",{onEnd:() => ended++});
  const old = spoken[0];
  voices = [];
  speech.speak("新回覆");
  old.onend(); old.onerror();
  loadVoices([cantonese]);
  assert.equal(ended,0);
  assert.equal(spoken.at(-1).text,"新回覆");
  assert.ok(!states.includes("audio-error"));
});


test("English mode chooses English speech and cancels queued Cantonese", () => {
  speech.speak("舊回覆");
  const stale = [...handlers];
  speech.setLanguage("en");
  const english = {name:"English",lang:"en-US"};
  loadVoices([cantonese,english]);
  stale.forEach(callback => callback());
  assert.equal(spoken.length,0);
  speech.speak("Hello, how can I help?");
  assert.equal(spoken.length,1);
  assert.equal(spoken[0].voice,english);
  assert.equal(spoken[0].lang,"en-US");
});

test("English mode does not silently fall back to a Chinese voice", () => {
  speech.setLanguage("en");
  voices = [cantonese,mandarin];
  speech.speak("Hello");
  expire();
  assert.equal(spoken.length,0);
  assert.equal(states.at(-1),"english-unavailable");
});

test("the language switch also controls browser recognition", () => {
  let recognition;
  globalThis.SpeechRecognition = class {constructor() {recognition=this;}};
  try {
    const controller = createSpeechController();
    controller.setLanguage("en");
    assert.equal(recognition.lang,"en-US");
    controller.setLanguage("zh-Hant");
    assert.equal(recognition.lang,"zh-HK");
  } finally {delete globalThis.SpeechRecognition;}
});
