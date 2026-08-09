import test from "node:test";
import assert from "node:assert/strict";
import { createVoiceCapture } from "../frontend/voice-capture.js";
test("cancel during permission request releases late stream without recording", async () => {
 let resolve, stopped=0, created=0;
 const capture=createVoiceCapture({mediaDevices:{getUserMedia:()=>new Promise(r=>{resolve=r})},MediaRecorderClass:class {},AudioContextClass:class {constructor(){created++;throw new Error("Must not start")}}});
 const states=[];
 const pending=capture.start({onStateChange:s=>states.push(s)});
 capture.cancel();
 resolve({getTracks:()=>[{stop(){stopped++}}]});
 assert.equal(await pending,false);
 assert.equal(stopped,1); assert.equal(created,0);
 assert.equal(states.at(-1),"ready");
});
