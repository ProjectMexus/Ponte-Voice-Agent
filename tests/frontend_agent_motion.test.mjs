import assert from "node:assert/strict";
import {beforeEach, test} from "node:test";
import {readFile} from "node:fs/promises";
import {createDOM, createEvent} from "./helpers/dom-fixture.mjs";

const source = await readFile(new URL("../frontend/agent-motion.js", import.meta.url), "utf8");
const {createAgentMotion} = await import(`data:text/javascript;base64,${Buffer.from(source).toString("base64")}`);
let motion, nodes, timers, ignoredCallbacks, fixture, actionCalls, prefersReduced, nextTimer;
beforeEach(() => {
  fixture = createDOM();
  globalThis.document = fixture.document;
  nodes = {};
  const add = (tag, id, parent) => (nodes[id] = fixture.add(tag, id, parent));
  add("section", "root");
  add("div", "strip", nodes.root).hidden = true;
  add("strong", "title", nodes.strip);
  add("p", "detail", nodes.strip);
  add("button", "skip", nodes.strip);
  add("div", "pointer", nodes.root).style = {};
  add("button", "replay").hidden = true;
  add("div", "time", nodes.root).setAttribute("data-field-key", "time");
  add("button", "slot", nodes.root).setAttribute("data-field-key", "slot_0");
  add("button", "approve", nodes.root);
  nodes.time.textContent = "14:00";
  nodes.approve.textContent = "確認掛號";
  nodes.root.getBoundingClientRect = () => ({top:0,left:0,width:800,height:600});
  nodes.time.getBoundingClientRect = () => ({top:200,left:24,width:700,height:48});
  actionCalls = [];
  const issued = {type:"confirmation_decision",decision:"approve",action_id:"SERVER-ACTION"};
  nodes.approve.addEventListener("click", () => actionCalls.push(issued));
  nodes.slot.addEventListener("click", () => actionCalls.push("slot"));
  prefersReduced = false;
  timers = new Map();
  ignoredCallbacks = [];
  nextTimer = 0;
  motion = createAgentMotion({root:nodes.root,strip:nodes.strip,title:nodes.title,detail:nodes.detail,
    pointer:nodes.pointer,skipButton:nodes.skip,replayButton:nodes.replay,
    reducedMotion:() => prefersReduced,
    schedule:(callback,delay) => {const id=++nextTimer;timers.set(id,{callback,delay});return id;},
    unschedule:(id) => {const timer=timers.get(id);if(timer) ignoredCallbacks.push(timer.callback);timers.delete(id);},
  });
});
function response(events, task="T1") {return {task:{task_id:task},workspace:{activity:events}};}
function event(id="E1",kind="service_lookup",extra={}) {return {id,kind,title:"查詢可用時段",detail:"已收到服務回覆。",status:"completed",operation:"slots",...extra};}
function tickThrough(delay) {
  const ready=[...timers].filter(([,timer]) => timer.delay <= delay);
  ready.forEach(([id,timer]) => {timers.delete(id);timer.callback();});
}

test("ordinary conversation and repeated cumulative evidence never invent a replay", () => {
  assert.equal(motion.play({response:{display_text:"你好"}}),false);
  assert.equal(timers.size,0);
  assert.equal(nodes.strip.hidden,true);
  motion.play(response([event()]));
  motion.cancel();
  assert.equal(motion.play(response([event()])),false);
  assert.equal(timers.size,0);
  assert.equal(nodes.replay.hidden,false);
});

test("only new events replay in server order and IDs are scoped to each task", () => {
  motion.play(response([event()]));
  motion.cancel();
  motion.play(response([event(),event("E2","draft_prepared",{operation:undefined,title:"已準備候選草稿"})]));
  assert.equal(nodes.title.textContent,"已準備候選草稿");
  motion.cancel();
  assert.equal(motion.play(response([event()],"T2")),true);
  assert.equal(nodes.title.textContent,"查詢可用時段");
});

test("pointer only highlights read-only current data and never clicks or changes focus", () => {
  nodes.time.focus();
  motion.play(response([event("E1","confirmation_ready",{operation:undefined})]));
  tickThrough(300);
  assert.equal(nodes.time.classList.contains("agent-pointed"),true);
  assert.equal(nodes.slot.classList.contains("agent-pointed"),false);
  assert.equal(nodes.approve.classList.contains("agent-pointed"),false);
  assert.deepEqual(actionCalls,[]);
  assert.equal(fixture.document.activeElement,nodes.time);
  assert.equal(nodes.approve.disabled,false);
  assert.match(nodes.pointer.style.transform,/translate3d/);
});

test("skip and cancellation prevent stale timers from highlighting a later result", () => {
  motion.play(response([event()]));
  nodes.skip.click();
  ignoredCallbacks.forEach(callback=>callback());
  assert.equal(motion.active,false);
  assert.equal(nodes.strip.hidden,true);
  assert.equal(nodes.pointer.hidden,true);
  assert.equal(nodes.time.classList.contains("agent-pointed"),false);
  assert.equal(timers.size,0);
  nodes.replay.click();
  tickThrough(300);
  assert.equal(motion.active,true);
  motion.cancel();
  assert.equal(nodes.time.classList.contains("agent-pointed"),false);
});

test("the user's actual action stops replay and retains its exact issued event", () => {
  motion.play(response([event()]));
  nodes.root.dispatchEvent(createEvent("click"));
  nodes.approve.click();
  assert.equal(motion.active,false);
  assert.deepEqual(actionCalls,[{type:"confirmation_decision",decision:"approve",action_id:"SERVER-ACTION"}]);
});

test("reduced motion and failed queries do not animate successful selections", () => {
  prefersReduced=true;
  assert.equal(motion.play(response([event()])),false);
  assert.equal(timers.size,0);
  assert.equal(nodes.replay.hidden,true);
  assert.equal(nodes.time.textContent,"14:00");
  prefersReduced=false;
  motion.play(response([event("E2","service_lookup",{status:"failed"})]));
  tickThrough(300);
  assert.equal(nodes.time.classList.contains("agent-pointed"),false);
  assert.equal(nodes.detail.classList.contains("agent-pointed"),true);
});

test("explicit clear invalidates replay targets and session reset clears observed IDs", () => {
  motion.play(response([event()]));
  motion.play({workspace:null});
  assert.equal(motion.active,false);
  assert.equal(nodes.replay.hidden,true);
  nodes.replay.click();
  assert.equal(motion.active,false);
  motion.reset();
  assert.equal(motion.play(response([event()])),true);
});

test("manual replay uses this turn's new events and completing removes all highlights", () => {
  motion.play(response([event()]));
  motion.cancel();
  motion.play(response([event(),event("E2","conflicts_checked",{operation:undefined,title:"已核對預約時間"})]));
  motion.cancel();
  nodes.replay.click();
  assert.equal(nodes.title.textContent,"已核對預約時間");
  tickThrough(1000);
  assert.equal(motion.active,false);
  assert.equal(nodes.pointer.hidden,true);
  assert.equal(nodes.time.classList.contains("agent-pointed"),false);
});

test("cash lookup highlights the returned benefit facts", () => {
  const amount = fixture.add("div", "amount", nodes.root);
  amount.setAttribute("data-field-key", "amount");
  amount.getBoundingClientRect = nodes.time.getBoundingClientRect;
  motion.play(response([event("E1", "service_lookup", {operation:"cash"})]));
  tickThrough(300);
  assert.equal(amount.classList.contains("agent-pointed"), true);
  assert.equal(nodes.time.classList.contains("agent-pointed"), false);
  assert.deepEqual(actionCalls, []);
});