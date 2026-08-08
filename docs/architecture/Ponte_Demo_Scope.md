# Ponte — Active Demo Scope

Status: active scope, 13 October 2026. Planning only; no application changes implemented by this scope update. The previous [implementation plan](Ponte_Implementation_Plan.md) and [architecture decision](Ponte_Architecture_Decision.md) are postponed future work. Their SVGs illustrate that future architecture, not the demo implementation.

## Demonstration goal

Demonstrate a real, bounded LLM tool-selection loop over existing MCP tools, with explicit human confirmation and a verified mock booking result. The single primary story is cardiology: request next Tuesday afternoon → find 14:00 and 15:30 → propose 14:00 as P1 → user changes to after 3 PM → invalidate P1 → propose 15:30 as P2 → explicit approval → book → show receipt.

Keep the existing UI, HTTP server, canonical `/api/interactions` envelope, voice adapter, `InteractionCore`, `ExecutionPipeline`, MCP transport and JSON-backed mock services. Preserve existing examination booking, appointment queries and cash-sharing demos on their current workflow paths. Do not replace the whole runtime or merge/remove legacy modules.

## In scope

| Capability | Demo implementation boundary |
|---|---|
| Actual agent integration | Add a small medical demo workflow adapter behind an explicit demo-agent setting. `InteractionCore` routes new cardiology demo tasks to it; a task stays with its original engine. Reuse `RegistryDrivenAgent` parsing/schema projection and `ChatCompletionClient`, extending only the transcript/proposal behavior necessary for this story. No separate general-purpose orchestrator. |
| Model-selected tools | Allow only `medical.list_departments`, `medical.search_registration_slots`, `medical.create_registration` for this agent path. One call per decision, bounded steps; reject unsupported/multiple calls before execution. Server supplies identity/context. |
| Stateful conversation | Keep task, transcript, intent revision and pending proposal in server memory for one running demo. Preserve assistant call IDs and paired tool results across approval turns. On intent change, close P1's call with `SUPERSEDED` before appending the new user message. |
| Explicit approval | Store immutable final input, task/session binding, revision, proposal ID, digest, expiry and issued action IDs in memory. Only the server-issued confirmation button/action authorizes booking. The model and transcribed “yes” cannot approve. Invalidate P1 on accepted intent change; validate P2 again before dispatch. |
| Duplicate and concurrent requests | Use a per-session lock around the complete demo turn, including model/dispatch, to serialize that session. Add an in-process medical backend lock around idempotency lookup, capacity check, booking and replay save. Stable proposal-derived idempotency key; sequential/concurrent duplicate approval returns the existing result. This deliberately favors simplicity over throughput. |
| Mock availability | Add injectable, reproducible cardiology fixtures with 14:00 and 15:30 slots. Tests freeze Oct 13 → next Tuesday Oct 20, 2026; live demo resolves dates from the service clock and seeds an isolated demo dataset accordingly. Do not overwrite existing booking data. |
| Verified success | Require matching patient, department, slot and start time, `Appointment.status == "booked"`, completed backend task and a valid `MED-REG-*` receipt. Display actual backend facts; model text alone cannot report success. |
| Safe failure | Stale P1 approval never dispatches. Slot unavailable produces recovery and a new proposal requiring approval. Step/protocol error produces a clear pause. An ambiguous booking timeout stops further demo booking attempts; no automatic write retry or new key. |
| Frontend/voice | Reuse opaque server action forwarding and existing confirmation/receipt views. Show cardiology/date/time/location clearly. Voice transcriptions enter the same demo workflow; existing STT/TTS stay. No UI redesign or new streaming transport. |
| Evidence | Deterministic scripted-model end-to-end tests over real MCP/backend, existing regression tests and a rehearsed presentation flow. A real-model smoke verifies tool selection; disclose scripted/reproducible mode if used in a presentation. |

## Tool contracts and primary acceptance

Use the existing registry contracts, not invented tool names:

1. `medical.list_departments`: input `{keyword:"Cardiology", active_only:true}` → `DEPT-CARDIO`.
2. `medical.search_registration_slots`: input `{department_id:"DEPT-CARDIO", date:"2026-10-20", session:"afternoon"}` → fixture slots at 14:00 and 15:30. There is no `after_time` parameter; re-evaluate the returned timezone-aware times or repeat this search.
3. P1/P2 freeze final `medical.create_registration` input `{patient_id:<server patient>, department_id:"DEPT-CARDIO", slot_id:<selected server slot>, consent:true}`, with matching `doctor_id` if supplied. The server injects trusted context and the stable idempotency key. Consent is a business field, not the approval credential.

No booking call is sent for P1. Changing intent invalidates P1 and creates a new P2; replaying P1 fails. Approving P2 twice results in one booking in the supported running-process demo. The returned `booked` status and receipt confirm 15:30. A model response containing two calls executes neither.

If an approval wins the per-session lock and booking starts before a later intent-change request, finish or classify that booking first. Do not promise the later request cancels an already submitted transaction. A browser abort does not cancel server execution.

## Explicitly deferred / not claimed

* Shared SQLite authority, medical JSON migration, crash-atomic booking/approval/idempotency records, durable task store, leases/CAS, background recovery and operation lookup tool.
* Restart/resume of pending approvals or transactions; multi-process/multi-host concurrency and throughput guarantees.
* Real patient authentication/delegation, independent backend verification of proposal approval, and production authorization. The demo uses the configured mock identity and runtime approval checks; backend continues its existing domain/patient/consent validation.
* Autonomous cross-domain mutations, cancellation/rescheduling, SDK adoption, deletion/merging of legacy components and general workflow infrastructure.
* Exactly-once external execution. The in-process locks do not fix crash gaps between JSON writes.

On restart, pending in-memory proposals are lost and cannot be approved. Existing backend bookings remain subject to current persistence behavior. After an ambiguous write outcome, display “outcome needs checking” and block new demo bookings for the configured patient in that process. An operator must inspect backend records before a rerun/restart; restarting is not a recovery mechanism or proof that no booking occurred. Do not erase the dataset to hide an uncertain result. This operating constraint is acceptable only for the supervised local mock demo.

## Small implementation sequence

1. Add isolated cardiology fixtures and scripted model acceptance story; preserve baseline regressions.
2. Introduce the demo workflow adapter and narrow tool allowlist; connect it to canonical text/voice routing without changing legacy tasks.
3. Implement in-memory transcript/proposal/revision handling, explicit action validation and per-session serialization.
4. Add the narrow in-process backend write lock, stable idempotency use, result verification and fail-closed timeout behavior.
5. Verify the full presentation story, stale/duplicate approvals, intent/approval ordering, slot loss and timeout; rehearse both real-model and disclosed reproducible modes.

Scope completion means that supervised local demonstration passes those checks while the existing app still works. It does not mean the postponed architecture has been implemented. Establish a revised effort estimate from this smaller adapter change before scheduling implementation; the previous 26–39 person-day estimate applies only to future work.
