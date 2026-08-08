# Ponte — Dependency-Ordered Implementation Plan

> **POSTPONED — FUTURE WORK (13 October 2026).** Per the revised project scope, phases 0–6 below are not the current implementation commitment. They describe the fuller durable architecture and remain as reference. Active work is limited to [Ponte_Demo_Scope.md](Ponte_Demo_Scope.md). Its explicit demo limitations supersede the production/reliability requirements below for this local demonstration; do not describe the demo as implementing those deferred guarantees.

Status: engineering plan only; application refactor not performed. Date: 13 October 2026. Implement the contracts and state machines in [Ponte_Architecture_Decision.md](Ponte_Architecture_Decision.md); that document is the authority if a phase description is abbreviated. Diagrams: [system](Ponte_System_Architecture.svg), [medical sequence](Ponte_Execution_Sequence.svg).

## Delivery boundary and estimates

When the full architecture is resumed, implement phases 0→1→2→3→4 in order for its **minimum durable end-to-end agent integration**. It includes durable approval, backend atomicity, basic restart/reconciliation and the mandatory intent-change scenario. Phase 5 broadens failure/security coverage and operations readiness; phase 6 removes obsolete paths only after parity. These phases are deferred in their entirety; the active local demo uses the narrower controls and disclosed limitations in the demo scope document. Keep unrelated frontend styling, HTTP framework changes, OAuth, real government integration and deployment redesign out of this work.

Estimates are focused engineering person-days including tests/review, assuming familiarity with Python and the repository. They are planning estimates, not elapsed-time promises: minimum 19–28 person-days; subsequent hardening/cleanup 7–11; total 26–39. Two students can parallelize contract-independent work after phase 1, but shared approval/backend semantics need one reviewer. A short demo deadline should reduce supported domains, not omit the execution ledger.

| Phase | Dependencies | Effort | Release gate |
|---|---|---:|---|
| 0. Baseline and contract fixtures | None | 1–2 days | Inspected baseline reproducible, existing changes protected. |
| 1. Shared durable state and transitions | 0 | 4–5 days | SQL constraints, CAS, ownership, transcript pairing tested. |
| 2. Atomic medical backend | 1 | 4–6 days | Approved medical operation commits atomically; exact replay/lookup works. |
| 3. Approval and trusted pipeline | 1, 2 | 3–5 days | No write bypass; pre-send admission durable and version-bound. |
| 4. Canonical agent integration | 3 | 7–10 days | Complete P1→intent change→P2 scenario and required failures pass. |
| 5. Reliability/security hardening | 4 | 4–6 days | Extended fault matrix, operational and protocol checks pass. |
| 6. Cutover and controlled cleanup | 5 | 3–5 days | One authoritative path; legacy removal justified by regression evidence. |

## Phase 0 — Protect the working application and freeze acceptance data

**Objective.** Establish the actual baseline, production path and deterministic tests before moving ownership.

**Existing files to inspect/modify.** Preserve all pre-existing uncommitted changes in frontend, middleware and medical backend. Inspect `middleware/tests/test_interaction_http.py`, `test_interaction_architecture.py`, `test_medical_workflow.py`, `test_agent.py`, `test_approval.py`; `tests/test_full_stack_integration.py`, `tests/test_frontend_interaction_contract.py`, `tests/medical/test_medical_backend.py`, `tests/test_persistence_restart.py`, `tests/core/test_idempotency.py`, frontend Node behavior tests and stack runner. Modify tests only when adding baseline fixtures; do not weaken assertions to accommodate unimplemented behavior.

**New files.** `tests/fixtures/agent_scenario.py`; `middleware/tests/test_runtime_acceptance.py` initially with explicit skipped future cases and an executable baseline characterization; no production feature change yet.

**Functions/data.** Add deterministic `cardiology_scenario(clock)` returning department/doctor/location and two outpatient Slot records: `SLOT-REG-20261020-CARDIO-1400`, `SLOT-REG-20261020-CARDIO-1530`; frozen clock `2026-10-13T09:00:00+08:00`. Test fixtures are injected, not silently written into existing demo data. Add fake `ChatCompletionClient` scripts that emit actual registry tool names and stable call IDs. Define shared assertions for expected wire response keys and no-write-before-approval.

**Reuse.** Existing test transports, `FixedClock`, backend request fixtures, real stdio integration helpers, canonical UI tests. Read current function signatures before adapting helpers; do not fabricate production method names.

**Tests/acceptance.** Record baseline commands/results for `python -m unittest discover -s middleware/tests`, `-s MCP/tests`, `-s tests`, and `node --test tests/*.test.mjs` with repository-required runtime/network permissions. Existing failures must be isolated and recorded before refactor. Characterize the present ignored follow-up utterance, sequential duplicate confirmation and dormant agent wiring. Prove fixture produces exactly two cardiology afternoon slots. Confirm no existing application file is overwritten with a clean-commit version.

**Risks.** Dirty working tree contains completed UI work; stale handoff notes are not the active task. Tests that assert exact source strings/counts encode old ownership. Preserve behavior checks, identify which structural assertions will intentionally change. **Gate:** checked baseline plus reviewed fixtures and a mapping from each existing route to its current engine.

## Phase 1 — Durable task/proposal/operation records and pure transitions

**Objective.** Establish one authoritative state model before connecting the LLM to execution.

**Existing files to modify.** `middleware/task_manager/contracts.py`, `transitions.py`; `middleware/contracts.py`; `middleware/session.py`; `middleware/interaction_contracts.py`. Extend contracts additively for legacy callers until phase 6. Do not yet delete `TaskManager` or switch core routing.

**New files.** `database/ponte_store.py`; `middleware/task_store.py`; `middleware/tests/test_task_store.py`, `test_runtime_transitions.py`, `test_runtime_transcript.py`. Store SQL migrations as versioned constants in `database/ponte_store.py` for this small schema, avoiding a new migration framework.

**Classes/functions to implement.** `Principal`, `TaskSnapshot`, `Proposal`, `Operation`, `TurnLease`, `IntakeResult`, `CommitResult`, typed state enums; `SQLiteTaskStore.ingest/load/claim_turn/commit_decision/snapshot`; `UnitOfWork`; pure `validate_task_transition`, `validate_proposal_transition`, `append_tool_result`, `close_pending_call`. Connection helper sets foreign keys, busy timeout, local-disk WAL and durable synchronization. Transactions use explicit `BEGIN IMMEDIATE`; one connection per thread.

**Interfaces/data models.** Implement the decision document's records and uniqueness constraints, including one patient-wide medical mutation reservation across all sessions/tasks. Keep `Task.version` separate from `intent_revision`; use database `version` CAS on each mutation and persisted fencing generation for model work. Store schema version, prompt/model versions, owner/session/engine binding, stable issued action IDs, event hash and monotonic inbox sequence. Transcript rows support structured assistant `tool_calls` and exact matching result ID; never overwrite a result. Pending call remains open only while paused. Canonical hashing rejects nonfinite/duplicate-key JSON. Private principal/context values never enter public snapshots.

**Reuse.** Immutable JSON freezing/serialization ideas in `PendingToolProposal`, `ToolCall`, `ToolExecutionResult`; pure transition/recovery concepts in task manager. Do not reuse a plain object hash as authorization or mutable `SessionState` as authority.

**Tests.** T01 owner/session isolation; T02 same interaction ID same payload deduplicates, different payload 409; T03 SQLite uniqueness gives one active proposal/operation and one result per call; T04 concurrent CAS permits one decision; T05 stale/expired turn lease cannot commit; T06 P1 closure precedes a new user prompt and tool result cannot be replaced; T07 reopen database reconstructs PENDING task/actions/transcript; T08 illegal task/proposal transitions rejected, terminal outcome cannot regress.

**Acceptance.** Two independent store connections concurrently update the same task with deterministic winner; no live mutable state escapes the store. Invalidated P1 persists for audit and cannot be restored. Public snapshot has current version and no secrets. Legacy tests still pass because runtime is not switched.

**Risks.** Coarse SQLite writer lock is acceptable only with short transactions. A model call inside a transaction is a release blocker. Add transaction-boundary assertions/tests. **Effort:** 4–5 days.

## Phase 2 — Authenticated atomic medical operation and exact reconciliation

**Objective.** Make the backend capable of validating a stored authorization and atomically recording its outcome. This must precede live agent writes.

**Existing files to modify.** `mock_backends/medical/service.py`, `backend.py`, `contracts.py`, `fixtures.py`; `mock_backends/server.py`; `MCP/registry.py`, `models.py`, `rest_adapter.py`; `scripts/run_stack.py`; relevant `docker-compose.yml`, Render/entrypoint configuration only to mount/configure the same local DB path; existing medical/persistence tests.

**New files.** `mock_backends/medical/store.py`; `scripts/migrate_medical_store.py`; `tests/medical/test_authorized_operations.py`, `test_medical_sqlite_atomicity.py`; `MCP/tests/test_operation_lookup.py`. Use `database/ponte_store.py` from phase 1, not a second database schema owner.

**Classes/functions.** `MedicalStore.book_with_authorization`, `get_operation`, SQL-backed medical record reads and ID generation; `MedicalBackend` authenticated caller resolution; `MedicalService` delegates writes to the unit of work while preserving domain validation/routes. Atomic UoW includes approval consumption, slot/date/capacity validation, duplicate check, booking/backend Task/receipt and exact replay response. Return domain errors as committed terminal rejection responses; do not raise an exception that rolls back the rejection record. Authorization failures cannot consume another patient's operation.

**Interfaces/data.** Preserve current medical payloads and tool names; add `operation_id` to hardened success/rejection envelopes and trusted context/header mapping `X-Ponte-Operation-Id`. Add `medical.get_operation` exactly as defined in the decision (R0, patient scoped, input `{operation_id}`, status/result/hash response). Extend `ContextRequirements` with operation ID for hardened writes. Backend validates configured service credential and server patient mapping; header possession without valid proposal/operation is insufficient. Keep `Idempotency-Key` stable and compare request hash before returning any saved response. Authentication and current task/proposal checks occur at business commit, not solely in HTTP middleware.

**Storage migration preparation.** Build and test migration of only medical appointments, backend tasks, IDs/legacy idempotency responses into shared SQLite; leave one-account/welfare JSON untouched. **Do not switch the running application's default backend in phase 2.** Instantiate hardened `MedicalBackend`/`MedicalStore` only in explicit test composition with an isolated DB/fixtures. Default legacy JSON-backed app stays unchanged. The actual writer-stop/import/activation is coordinated with the fallback adapter in phase 3. The migration stops medical writers, backs up source files, validates counts/IDs/hashes, imports in a transaction, then switches medical reads and writes together. Preserve IDs/references and import legacy replay records as legacy evidence without fabricating approvals. Existing medical records remain queryable. Do not dual-write business records. An empty test/demo DB can initialize directly. Add `PONTE_STATE_DB` absolute/local-volume path shared by both processes; scripts verify same resolved path. No network database is introduced.

**Reuse.** Existing domain department/doctor/slot validation, date-window helper, response shape and medical read routes. Current `RecordRepository` per-record operations and `RepositoryIdempotencyStore` are insufficient as the atomic UoW; do not wrap individual writes and call them transactional.

**Tests.** B01 invalid credential, wrong owner/patient, missing operation, stale revision, body/key mismatch fail without booking; B02 approved registration returns `booked`/`MED-REG-*` with correct facts; B03 same key replay returns exact saved response after restart/expiry; B04 two concurrent identical keys yield one booking; B05 different keys competing for last capacity yield one success; B06 fault injected before each write and before commit leaves all-or-none records; fault after commit leaves replayable success; B07 lookup returns exact operation/result/receipt, 404 for unknown/other patient; B08 slot/date/doctor mismatch or expiry commits stable no-effect rejection; B09 migration preserves legacy data and has safe rerun guard.

**Acceptance.** In the explicit hardened test composition, direct MCP/REST calls cannot bypass the approval ledger. New backend tests use a test-only helper that creates real authorized records; do not ship a production bypass flag. Baseline app/full-stack tests still use unchanged legacy composition until phase 3. Operation lookup over hardened real stdio/HTTP correlates receipt to exact slot/key. Atomicity tests use separate connections/process termination, not only mocked exception success.

**Risks.** Shared-volume path misconfiguration, nontransactional ID counters, and returning a response before commit. Fail closed if DB/schema is unavailable. Keep local dev legacy writers explicitly separate until phase 3 adapts them; never claim they are hardened. **Effort:** 4–6 days.

## Phase 3 — Proposal-bound approval and one trusted execution pipeline

**Objective.** Make approval/admission enforcement unavoidable for every supported medical write.

**Existing files to modify.** `middleware/approval.py`, `execution.py`, `contracts.py`, `medical_workflow.py`, `controller.py`, `server.py`; `MCP/rest_adapter.py` full validation; `middleware/tests/test_approval.py`, `test_execution.py`, `test_medical_workflow.py`, `test_interaction_architecture.py`. Update backend contract consumers consistently.

**New files.** `middleware/medical_policy.py`; `middleware/tests/test_execution_authority.py`, `test_proposal_binding.py`; root dependency manifest `requirements.txt` if none exists (jsonschema 4.x, exact patch pinned during implementation) and corresponding container install change. No new gateway service/class.

**Classes/functions.** Replace `ApprovalGate` with `ApprovalService.propose/decide`; implement `ExecutionRequest`, `ExecutionObservation`, `InputPolicyStage`, `AuthorizationJournalStage`, `ResultVerificationStage`; adapt existing `ExecutionPipeline.dispatch` and stage protocol to typed requests and retain `McpExecutionStage` terminal. Extract `build_medical_proposal_input`, `validate_selected_slot`, `verify_medical_result`, `build_action_receipt` into medical policy. `ResultVerificationStage` wraps terminal call and validates on return. LLM approval classification is never called to grant permission.

**Interfaces/data.** Approval action binds random persisted action ID, principal/task/proposal, intent revision, proposal digest, permitted decision and UTC TTL. `confirmation_id` remains wire alias for proposal ID. Keep full outbound `input_hash` separate from broader `proposal_digest`. Proposal body includes server patient and exact selected slot; consent true is the intended outbound business value, not proof. Approve transaction creates one PREPARED operation while task stays AWAITING_APPROVAL; pipeline admission rechecks current bindings and persists DISPATCHED/task EXECUTING before network send. No new random idempotency key per retry. Post-admission edits queue; pre-admission changes invalidate/cancel atomically.

**Reuse and coordinated activation.** Existing pipeline continuation composition, stdio terminal, fixed registry and transport errors; existing receipt/workspace projections. Fallback `MedicalWorkflow` now creates and decides **the same** durable proposal/operation, entering the same pipeline, rather than continuing its private confirmation authority. Keep its step-by-step UI until phase 6. Only after this adapter passes hardened test composition, stop intake/writers, cancel old in-memory confirmations with explicit reconfirmation, perform phase-2 migration and switch backend+middleware together to the hardened store. Do not expose hardened backend to an incompatible legacy writer and do not add a bypass for migrated data. Keep diagnostic reads; disable diagnostic mutations in secure mode and route any explicit developer mutation through real authority fixtures, not production bypass.

**Tests.** E01 unknown tool/type/enum/extra input/model-supplied context/patient fails before dispatch; E02 no R1/R2 dispatch on proposal creation; E03 expired new decision, invalidated/wrong-task/wrong-owner/stale/conflicting action replay fails; E04 identical owner/action/decision duplicate and different interaction IDs resolve one operation, including receipt retrieval after TTL without fresh authorization; E05 barrier between approval and admission lets intent edit invalidate PREPARED; E06 barrier after admission queues intent and preserves frozen revision; E07 timeout CAS cannot overwrite terminal success; E08 wrong patient/department/slot/start/status/operation/receipt is unverified; E09 default server/raw tool/legacy/fallback entrypoints cannot bypass mutation checks.

**Acceptance.** All supported medical writes have a durable operation before send and verified result before success. Existing examination booking still renders confirmation and receipt through the common gate. Do not delete legacy `InteractionCore` or workflows. Generic R1/R2 tools that lack hardened backend support are denied by allowlist with clear recovery.

**Risks.** Allowing optional authority parameters to become permanent bypasses; confusing raw transport `ok` with verified outcome; schema drift between model projection and full tool input. A temporary legacy adapter is explicitly removed in phase 6. **Effort:** 3–5 days.

## Phase 4 — Minimum viable canonical agent integration

**Objective.** Connect real model-selected tools to canonical HTTP/voice tasks and pass the mandatory scenario, including restart/race variants.

**Existing files to modify.** `middleware/agent.py`, `llm_transport.py`, `interaction_core.py`, `server.py`, `interaction_contracts.py`, `interaction_delivery.py`, `interaction_voice.py`, `voice_services.py`, `session.py`; `frontend/mcp-client.js`, `app.js`, `interaction-view.js` only for additive session/progress/reload/version behavior; `.env.example`, READMEs, stack runner; existing agent/canonical/voice/frontend tests.

**New files.** `middleware/runtime.py`; `middleware/tests/test_runtime_acceptance.py`, `test_runtime_http.py`, `test_runtime_recovery.py`; `tests/test_agent_full_stack.py`; `tests/frontend_runtime_progress.test.mjs`. Add no workflow framework.

**Classes/functions.** `AgentRuntime.handle/resume/tick`, intake/drive/observe/project helpers; `RegistryDrivenAgent.next_decision`; transcript reconstruction and superseded-call closure; bounded application thread pool; startup recovery scan. `InteractionCore.handle` forwards to runtime and owns no mutable task state on agent path. Retain legacy engine routing outside the agent task, pinned once at task creation. `CoreVoiceTurnProvider` continues to call this core.

**Model behavior.** Project only policy-approved tool schemas; omit trusted patient/consent/context fields from model inputs. Preserve native call IDs; JSON action mode generates IDs. Exactly one call per decision; whole-response rejection for multiple calls. Model receives structured read results, denied/superseded/expired tool observations, and verified write results. Model `respond` cannot complete a booking without the receipt. Eight decisions/20-second drive budget, 32 total task decisions; explicit continue action and handoff after ceiling. Clarification/budget persists resumable state.

Implement the decision's exact medical allowlist and `facts.flow_kind` while preserving wire task type `medical_appointment`. Runtime-only operation lookup is not a general model browsing tool. Preserve the existing serialized stdio client lock and recycle the child after timeout/protocol desynchronization before the next RPC; this is transport recovery, not evidence of cancellation or no effect. Include a late-old-RPC-response test in A04/A08.

**HTTP/UI.** Preserve POST `/api/interactions` and voice multipart; existing result keys stay unchanged. Add same-origin POST `/api/session` bootstrap with HttpOnly SameSite demo-principal cookie, owner/CSRF/origin checks and configured backend service credential. Add owner-checked GET `/api/interactions/state` snapshot; client polls processing/executing/reconciling and restores after reload. Order responses by monotonic `session_revision` for that session; compare task versions only for identical task IDs so a new task version1 supersedes old task version20. Confirmation actions remain opaque server events with bound metadata. Extend `WorkspaceProjector`/`ResponseComposer` with processing/reconciling and cardiology registration facts; generic confirmation renders department/date/time/location without pretending consultation is an examination. Do not change avatar/layout or invent client workflow logic. Voice “yes” is not executable approval; voice returns explicit confirmation card, and changes invalidate like text.

**Basic recovery.** Startup preserves PENDING proposals and closes expired calls. DISPATCHED/UNKNOWN operation enters reconciliation; call `medical.get_operation` using exact stored ID. Successful result verifies and completes, rejection closes call and replans, NOT_APPLIED permits same-key resend only under the hardened contract. After retry budget remain RECONCILING with needs-assistance and retain the patient-wide mutation reservation; a new session cannot bypass it. Basic bounded reconciliation and status polling are required here; expanded operational testing is phase 5. Queued input after successful commit starts a new linked task with a truthful booking disclosure; no automatic cancellation tool exists.

**Reuse.** Current small loop parsing/system prompt and `ChatCompletionClient`; canonical delivery/voice/STT/TTS; registry, MCP client, domain facts and fallback UI. Do not activate `RegistryVoiceTurnProvider`.

**Tests/acceptance.** A01 complete real HTTP→runtime→stdio MCP→medical backend trace with scripted LLM: discovery/search/14:00/P1/no write/after-3/P1 invalidation/SUPERSEDED/re-evaluation/15:30/P2/explicit approval/O2/verified receipt. Assert actual tool names and complete inputs/context. A02 approve P1 after invalidation → no write; A03 duplicate P2 → one key/booking; A04 timeout after commit → lookup same receipt; A05 capacity lost → stable rejection, new proposal required; A06 restart awaiting approval → same P2/actions until expiry; A07 concurrent message vs approval → both legal orderings tested with barriers; A08 restart admitted-before-send → same-key recovery; A09 read/query/cash, examination booking and voice parity; A10 step limit/multi-call/provider error → safe resumable pause; A11 interrupted browser request/late response/reload → current snapshot/version and no unintended cancellation; A12 user/voice text affirmative cannot grant approval; A13 cookie/session/CSRF/owner isolation.

**Release gate.** All A/B/E/T tests required for minimum scope pass. Real stdio/backend scenario and frontend opaque action forwarding pass. Success is drawn from `booked`+receipt for registration, `confirmed`+receipt for examination. No live LLM credentials are necessary for deterministic acceptance; one optional real-provider smoke checks protocol compatibility without substituting for the tests. Enable agent mode only for new local test sessions. Existing sessions stay pinned to their engine; old in-memory confirmations must be cancelled/reconfirmed, never imported as approvals.

**Risks.** Transcript/tool-call mismatch, stale model commits, missing cookie credentials in cross-origin dev, proxy timeout, or polling forever. Bound driver and pool; expose deterministic progress and correlation IDs. **Effort:** 7–10 days.

## Phase 5 — Reliability, protocol and operational hardening

**Objective.** Strengthen the already-correct minimum path under process loss, repeated transport faults, storage contention and malicious inputs.

**Existing files to modify.** `runtime.py`, `task_store.py`, `execution.py`, `medical_policy.py`, `MCP/registry.py`, `rest_adapter.py`, `mcp_client.py`, backend store, diagnostics/logging and deployment docs. Do not broaden domain write allowlist automatically.

**New files.** `tests/test_agent_fault_matrix.py`, `tests/test_agent_concurrency.py`, `middleware/tests/test_transcript_compaction.py`; `docs/architecture/Ponte_Operations.md` during implementation (not a deliverable of this review).

**Functions/interfaces.** Complete bounded reconciliation backoff 1/2/4/8/16 seconds and needs-assistance behavior; record next check/attempt metadata; recover expired leases with fencing; safe transcript compaction of completed exchanges only; path segment quoting/ID validation; response size/redaction limits; schema compatibility fail-closed behavior; audit export and operator inspection by operation ID. Keep idempotency/operation records while replay is possible. Define DB backup/restore procedure that never mixes a restored old task DB with newer medical state (one DB backup). No general replay/time-travel function for writes.

**Reuse.** Existing structured log/request IDs and backend errors. Fix the `service_type`/`type` catalog mismatch as a narrow contract correction with regression; do not bundle unrelated redesign.

**Tests.** H01 kill middleware/backend after each durable boundary and reopen; H02 duplicate same-key POST arrives after NOT_APPLIED lookup, only one commit; H03 lease expires while old LLM returns, no stale effect; H04 SQLite busy/disk-full/unavailable fails closed; H05 expired approved operation before backend admission returns stable no-effect rejection, committed replay still visible after expiry; H06 malformed 2xx/forged receipt/foreign operation has no success; H07 tool-output prompt injection cannot bypass policy or approve; H08 audio/transport cancellation does not affect operation state; H09 complete-history compaction retains call/result pairs and current intent; H10 owner/patient isolation across all reads/lookup/legacy diagnostics; H11 path/extra-field/oversize payload rejects; H12 backup restore and migration schema mismatch behavior documented/tested; H13 unresolved needs-assistance operation blocks new medical mutations from another session/task while reads and original reconciliation remain available.

**Acceptance.** Repeated randomized concurrent tests preserve one operation per proposal and capacity invariants; fault recovery always yields verified receipt, stable rejection, or explicit unresolved handoff—never fabricated completion. Check current stdio client serializes/waits safely under threaded callers; fix narrowly if tests reveal an issue. No tests claim more than the local backend contract proves.

**Risks.** Recovery path accidentally generates a new key; indefinite replay-record deletion; excessive log retention of medical details; same DB path on unsupported network storage. **Effort:** 4–6 days.

## Phase 6 — Cutover, rollback rehearsal and removal of duplicate ownership

**Objective.** Make the new path the default while keeping rollback honest about admitted external operations.

**Existing files to modify/remove.** Default composition in `server.py`, `InteractionCore`, `session.py`, `controller.py`, task manager, `medical_workflow.py`, `voice_services.py`, relevant tests/docs. Remove `RegistryVoiceTurnProvider`, obsolete `ApprovalGate`/authorization classifier path, old `RegistryDrivenAgent.run` execution wrapper, `ContextualExecutionPipeline` and `TaskManager` mutation class only after no production callers remain. Keep pure recovery models/helpers and STT/TTS adapters. Move remaining domain policy/projections before deleting workflow orchestration. Retain `InteractionCore` thin adapter unless a separate API cleanup is later justified; deleting it is not a goal.

**New files.** No new runtime components. Optional `THIRD_PARTY_NOTICES.md` only if implementation has actually copied/adapted code or requires dependency notices; document exact source/version and required license text.

**Classes/functions.** Remove temporary optional-authority/legacy write shims; every production write dispatch requires typed execution request. Retire diagnostic mutation routes in normal mode. Keep legacy read-only endpoints only where consumers exist; mark deprecation without forcing frontend migration.

**Reuse/tests.** Re-run original regression suites, frontend behavior tests, full stack A01 and B/E/H gates. Update structural/source tests to assert single authority and no bypass, rather than forbid newly centralized implementation strings. Test agent disabled/unavailable behavior explicitly: existing legacy task stays legacy, agent task never silently falls back to unsafe writer. Rehearse stop intake→reconcile admitted operations→backup→rollback; never restore an older writer while unknown operations remain. Snapshot route remains able to show old receipts.

**Acceptance.** No active runtime owns two task models. New-task default agent, confirmed regression parity; zero production references to removed paths; all schema versions handled explicitly. Review two SVGs against actual module names and update them when implementation finishes. Professor demo script shows P1 invalidation, P2 approval, MCP trace and verified receipt in two slides.

**Risks.** Deleting compatibility modules too early, resetting sessions and losing admitted operation visibility, enabling unsupported welfare/government mutations, or presenting local demo identity as production security. **Effort:** 3–5 days.

## Traceability matrix

Test IDs below are acceptance identifiers, not claims that these tests currently exist. Implement each in the named new/existing suites and link test function names back to IDs in docstrings. Keep deterministic barriers/fake clocks for ordering; do not rely on sleep races.

| Required capability | Implementation files / owner | Acceptance tests / phase |
|---|---|---|
| Actual canonical agent wiring | `server.py`, `interaction_core.py`, `runtime.py` | A01, A09; phase 4 |
| Registry schema projection / one next action | `agent.py`, `llm_transport.py`, `medical_policy.py` | E01, A10; phases 3–4 |
| LLM working history distinct from task authority | `task_store.py`, task contracts, `runtime.py` | T06/T07, H09; phases 1, 4–5 |
| Exact assistant call/result pairing on pause/change/resume | `agent.py`, `runtime.py`, transcript helpers | T06, A01/A06, A10; phases 1, 4 |
| Durable task lifecycle / leases / CAS | `task_store.py`, `transitions.py`, `runtime.py` | T04/T05/T08, H03; phases 1, 4–5 |
| Proposal-bound owner/action/version/expiry approval | `approval.py`, contracts/store, backend store | E02–E06, B01/B08, H05; phases 2–4 |
| Explicit human approval, no model authority | `approval.py`, `interaction_voice.py`, server/action UI | A12/A13, E03; phases 3–4 |
| Intent change during P1 approval | `runtime.py`, store, medical policy | A01/A02, E05; phases 3–4 |
| Preserve existing HTTP/frontend contract | `server.py`, `interaction_contracts.py`, delivery, client | A09/A11 plus existing contract tests; phase 4 |
| Reload/resume/progress polling | state endpoint, `mcp-client.js`, `app.js`, projector | A06/A08/A11; phase 4 |
| Backend validates approval and current task | `medical/backend.py`, `medical/store.py`, shared DB | B01/B08, A07; phases 2–4 |
| Persist irreversible intent before send | pipeline journal/store | E05/E06, A08, H01; phases 3–5 |
| Atomic booking/approval consume/idempotency response | `medical/store.py`, service | B03–B06; phase 2 |
| Concurrent same-key / final-capacity protection | medical UoW / SQL constraints | B04/B05, H02; phases 2, 5 |
| Duplicate approval / stale replay prevention | store/actions/approval/backend | T02/T03, E03/E04, A02/A03; phases 1–4 |
| Unknown-outcome reconciliation | runtime/pipeline, `medical.get_operation` registry/backend | B07, A04/A08, H01/H02/H05; phases 2, 4–5 |
| Unknown operation cannot be bypassed by new task/session | patient-wide reservation in store/approval/pipeline | H13 and minimum A04 variant; phases 1, 4–5 |
| No incorrect success from transport/model | verification stage, medical policy, composer | E08, A04/A05, H06; phases 3–5 |
| Slot changed after approval | backend medical UoW, runtime recovery | B05/B08, A05; phases 2–4 |
| Restart awaiting approval | SQLite store, runtime startup and state endpoint | T07, A06; phases 1, 4 |
| Concurrent message/approval and stale model response | admission/store/inbox/fencing | T04/T05, E05/E06, A07/H03; phases 1–5 |
| Bounded steps and safe protocol failure | agent/runtime, continue action | A10; phase 4 |
| Voice/text parity and browser abort semantics | core voice/runtime/frontend | A09/A11/A12, H08; phases 4–5 |
| Principal/patient isolation and safe diagnostic reads | server/policy/backend credential/session binding | T01, B01/B07, E09, A13/H10; phases 1–5 |
| Exact registration vs examination contracts | medical policy/registry/fixtures/projections | B02, A01/A09, existing medical tests; phases 0–4 |
| Medical JSON data preserved through narrow migration | migration script, medical SQL store | B09, H12; phases 2, 5 |
| No duplicate authority / safe legacy retirement | core/controller/task manager/workflows/composition | E09, phase 6 reference checks + full regression |
| Reference/license provenance | dependency manifest, notices only when applicable | Phase 6 source/dependency review; no upstream code copied in planning |

## Definition of done for an implementation phase

Each phase ends with a reviewable diff, updated test evidence and a report of active route ownership. Preserve the baseline app throughout. Passing unit tests alone does not enable medical writes: the real canonical HTTP→MCP→backend acceptance gate must also pass. A release candidate must explain admission cutoff, backend commit, unknown outcomes and demo identity limits without claiming exactly-once behavior for arbitrary external services.

These four architecture deliverables are the stopping point of the current review. None of the planned runtime modules, endpoints, migrations or backend guarantees should be described as implemented until the corresponding phase is completed and tested.
