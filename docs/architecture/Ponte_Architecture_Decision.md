# Ponte — Final Architecture Decision

> **FUTURE ARCHITECTURE — implementation postponed (13 October 2026).** The active delivery target is now the local demo defined in [Ponte_Demo_Scope.md](Ponte_Demo_Scope.md). The recommendation, interfaces, durable guarantees and two SVG diagrams below remain the longer-term target, not features required or claimed for the demo. Repository findings remain applicable.

Status: implementation specification; no runtime refactor implemented by this review. Reviewed 13 October 2026, Asia/Singapore. Repository baseline: `441fa9c78857a37dfb226f698614fcd64fbf40e7` **plus the existing uncommitted working tree**, including the current demo UI and medical projections. References below identify that inspected working tree, not an assertion about a clean commit. Existing application changes must be preserved.

## 1. Decision

Choose **A: retain and extend Ponte's existing runtime**. Evolve `RegistryDrivenAgent` into a resumable decision engine, introduce one `AgentRuntime` that owns task execution, and retain `ExecutionPipeline` as the single trusted dispatch boundary. Keep `InteractionCore` as a thin compatibility adapter. Merge `TaskManager` lifecycle responsibilities into the runtime and persistent transition helpers. Do not add an `AgentOrchestrator`, a second `TrustedToolGateway` dispatcher, a graph framework, another HTTP framework, or another service.

The current application is workflow driven. The final application lets the model select the next allowlisted tool while deterministic code controls identity, state transitions, approval validity, dispatch admission, and completion. The model's final text cannot mark a transaction complete.

Use **one local SQLite authority database**, `data/ponte-runtime.sqlite3`, shared by the middleware and the existing mock medical backend processes on one host. Runtime tables hold tasks, transcripts, proposals and admitted operations. A narrowly scoped medical unit of work atomically stores the booking, backend task, receipt, idempotency response and consumed proposal. This narrow storage change is necessary: existing separate JSON writes cannot make approval consumption and booking crash atomic. Other domain storage need not migrate. The deployment remains the existing UI, middleware/MCP subprocess, and mock backend; local containers mount the same persistent local volume. SQLite on a network filesystem, independent container-local copies, or multiple hosts is outside this design.

Two distinct points matter:

1. **Dispatch admission** is a durable `PREPARED → DISPATCHED` compare-and-set. Before it, an intent change may invalidate approval. After it, intent changes are queued until the admitted operation has a known outcome. This is the cancellation cutoff.
2. **Business commit** is the backend SQLite transaction that consumes approval and creates the booking and receipt. Admission is not evidence that a booking succeeded.

This conservative cutoff makes races explicit. An operation may be admitted but never sent because the process crashes. Recovery reconciles it and can resend only the identical operation/key under the strengthened backend contract. No blanket exactly-once external-execution guarantee is claimed.

## 2. What actually runs today

### Canonical path

```text
frontend/app.js submitTranscript / handleWorkspaceAction
 → MiddlewareClient.sendInteraction (frontend/mcp-client.js)
 → POST /api/interactions (middleware/server.py)
 → InteractionCore.handle
 → MedicalWorkflow.start/handle OR CashSharingWorkflow.start/handle
 → ExecutionPipeline.dispatch → McpExecutionStage.handle
 → McpStdioClient.call_tool → MCP/server.py tools/call
 → ToolRegistry.get → RestAdapter.invoke
 → MedicalBackend.handle → MedicalService / other mock backend
 → CanonicalInteractionResult → DeliveryOrchestrator.deliver → UI
```

Evidence: [frontend client](../../frontend/mcp-client.js#L81), [frontend utterance](../../frontend/app.js#L417), [composition](../../middleware/server.py#L85), [HTTP routing](../../middleware/server.py#L393), [core](../../middleware/interaction_core.py#L31), [execution](../../middleware/execution.py#L133), [MCP server](../../MCP/server.py), [adapter](../../MCP/rest_adapter.py#L108). Configured voice uses `CoreVoiceTurnProvider` around the **same** core: [server.py:489](../../middleware/server.py#L489), [interaction_voice.py:47](../../middleware/interaction_voice.py#L47). HTTP currently returns synchronous JSON. There is no canonical SSE implementation to preserve.

`RegistryDrivenAgent` is **not wired into `/api/interactions`**. Its current uses are isolated tests and optional `RegistryVoiceTurnProvider` in [voice_services.py:110](../../middleware/voice_services.py#L110); server composition uses `CoreVoiceTurnProvider`. `ApprovalGate` is similarly outside the canonical path. Setting an agent-looking environment variable is not evidence of active agent execution.

### Findings that change the design

| Implemented behavior / gap | Evidence and consequence |
|---|---|
| Follow-up text during an active medical task reprojects the current view without interpreting the message | `MedicalWorkflow.handle`, [medical_workflow.py:110](../../middleware/medical_workflow.py#L110). “After 3 PM” does not invalidate P1 today. Structured `modify` does clear selection at lines 207–215. |
| Canonical confirmation has only an ID and status | [medical_workflow.py:183](../../middleware/medical_workflow.py#L183). No frozen arguments, owner, intent revision, expiry or digest. |
| Approval executes before state is saved | [medical_workflow.py:217](../../middleware/medical_workflow.py#L217) and `InteractionCore._save`, [interaction_core.py:73](../../middleware/interaction_core.py#L73). A restart can lose submission knowledge. |
| Server threads can advance the same snapshot concurrently | `ThreadingHTTPServer`, [server.py:178](../../middleware/server.py#L178); `SessionStore` map locks return live mutable objects, [session.py:57](../../middleware/session.py#L57). A map lock does not serialize a task transaction. |
| Sequential duplicate confirmation is ignored; simultaneous duplicates can both dispatch | [medical_workflow.py:194](../../middleware/medical_workflow.py#L194). Stable confirmation-derived key exists at lines 235 and 386, but the backend must enforce it atomically. |
| `action_id` is required but not checked against an issued action | [medical_workflow.py:485](../../middleware/medical_workflow.py#L485). An opaque-looking ID is not an authorization check. |
| MCP schema enforcement checks required field presence only | [rest_adapter.py:132](../../MCP/rest_adapter.py#L132); registry schemas default to extra input properties, [registry.py:41](../../MCP/registry.py#L41). Full type/enum/extra-field validation is planned work. |
| Booking idempotency is lookup → execute → remember | [medical/service.py:46](../../mock_backends/medical/service.py#L46). Backend task, appointment, and replay response are separate writes at lines 218–231. Concurrent calls/crashes can produce effects without a replay record. |
| JSON storage locks individual file operations within one process | [core/persistence.py:14](../../mock_backends/core/persistence.py#L14), [core/persistence.py:99](../../mock_backends/core/persistence.py#L99). This does not serialize capacity check plus booking. |
| Identity is a configured demo patient, not authenticated end-user identity | [server.py:79](../../middleware/server.py#L79), [medical/contracts.py:16](../../mock_backends/medical/contracts.py#L16). Medical backend does not validate the forwarded Authorization credential today. |
| Verification checks shape but accepts any nonempty status | `_verify_medical_result`, [medical_workflow.py:567](../../middleware/medical_workflow.py#L567). It does not correlate all approved facts or distinguish `booked` from failed statuses. |
| Retry state and task state are process memory | [medical_workflow.py:45](../../middleware/medical_workflow.py#L45), [session.py:48](../../middleware/session.py#L48). Timeout is not explicitly modeled as an unknown transaction outcome. |
| Dormant agent cannot restore tool-call history | `_safe_history`, [agent.py:233](../../middleware/agent.py#L233), permits only user/assistant text; `_tool_exchange` pairs calls only inside one run. Parser discards native call IDs. |
| Dormant approval is not single use | [approval.py:81](../../middleware/approval.py#L81). It relies on an LLM classification plus an object hash/expiry, without durable consumption or task ownership. Plain SHA256 in [contracts.py:221](../../middleware/contracts.py#L221) is not authentication. |
| Optional agent voice path is unsafe to wire as-is | [voice_services.py:150](../../middleware/voice_services.py#L150) claims completion on `executed` and accesses `resolution.result`; contract field is `execution_result`, [contracts.py:294](../../middleware/contracts.py#L294). |

Existing architectural documentation is useful intent, not implementation proof. The [2026-08-06 design](../superpowers/specs/2026-08-06-voice-first-medical-interaction-core-design.md) explicitly excludes production task versioning, durable attempts and complex concurrency. [PonteArch.md](../PonteArch.md) describes a broader workflow-first ambition. This decision supersedes their execution/approval direction where inconsistent; it preserves their narrow demo scope.

## 3. Reference implementations and option selection

Primary source code and documentation were reviewed on 13 October 2026. Links below follow upstream `main` or live docs; a usable immutable upstream SHA was not obtained. They are design evidence, not pinned dependencies. No upstream code is copied in these deliverables. Pin and record a version/commit before any later dependency adoption or code adaptation.

| Reference | Adopt in Ponte | Assumptions / limits | Import decision |
|---|---|---|---|
| [OpenAI Agents SDK HITL server](https://github.com/openai/openai-agents-python/blob/main/examples/agent_patterns/human_in_the_loop_server.py), [`RunState`](https://github.com/openai/openai-agents-python/blob/main/src/agents/run_state.py) | Server-owned serialized suspended state; opaque decision IDs; owner checks; atomic claim before resume; versioned persisted state. | Example explicitly uses one-process/event-loop dictionary storage and calls for bounded retention and atomic owner-checked consume in production. Consuming a request does not make subsequent side effects recoverable. SDK run state is not an authoritative business transaction record. | No import for this refactor. Helpful later for provider/protocol breadth, but approval/operation ledger still custom. Handoffs, hosted execution and voice-stack replacement unnecessary. |
| [PydanticAI deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/), [approval wrapper](https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pydantic_ai/toolsets/approval_required.py), [agent graph](https://github.com/pydantic/pydantic-ai/blob/main/pydantic_ai_slim/pydantic_ai/_agent_graph.py), [MCP client](https://pydantic.dev/docs/ai/mcp/client/) | Typed deferred requests; exact `tool_call_id` correlation; schema checks; approval enforcement at execution; denied/superseded calls become observations. | Stop/resume requires preserved history plus deferred results. `_handle_deferred_tool_results` prevents replacing completed results; interrupted tails need explicit closure. Application owns persistence and identities; a shared MCP client has a shared identity unless explicitly changed. | Best SDK alternative: `pydantic-ai-slim` with tools delegating through Ponte's pipeline. Still adds SDK-state mapping. Never expose SDK MCP execution around the pipeline. |
| [LangGraph interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts), [checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers), [checkpoint base](https://github.com/langchain-ai/langgraph/blob/main/libs/checkpoint/langgraph/checkpoint/base/__init__.py) | Persist before interrupt; stable task ID; explicit resume; isolate side effects; test replay boundaries. | Resume reruns the interrupted node from its beginning. Pre-interrupt effects must be idempotent or isolated. Checkpoints/successful node writes do not atomically commit a remote booking or serialize arbitrary HTTP updates. | Reject graph/checkpointer dependency for one bounded loop. Reconsider if branching graphs and parallel durable workflows become central. No reducers, subgraphs or time travel now. |
| [smolagents loop](https://github.com/huggingface/smolagents/blob/main/src/smolagents/agents.py), [memory](https://huggingface.co/docs/smolagents/tutorials/memory) | Small bounded action/observation loop; inspectable step history; explicit errors. | Per-agent mutable memory is not a concurrent durable task store. `ToolCallingAgent` supports parallel calls; max-step fallback can ask the model for final text. Neither establishes transaction success. | No import: Ponte already has the useful small loop. Reject `CodeAgent`, model-written Python, remote executors and parallel mutation calls. |

These source-specific summaries are intentionally limited to the patterns relevant here. Their existence does not imply Ponte already implements them.

| Option | Maintainability | Incremental cost | Correctness / project fit |
|---|---|---|---|
| **A. Extend existing Ponte — selected** | One known tool registry, HTTP contract and execution path; small explicit state model. | Lowest: reuse loop, transports, UI and domain validation. | Domain-specific safeguards still required, with no second framework state authority. Fits student team and existing app. |
| B. Adopt lightweight SDK | Less provider-message plumbing; added dependency, SDK upgrades and state adapters. | Medium; migrate history/deferred-call format while still building domain ledger. | Mature loop reduces protocol errors but does not solve backend atomicity, replay or ownership. PydanticAI is the preferred future spike. |
| C. Build a new minimal runtime from scratch | Small code initially, but duplicates current parsing/loop/tests. | Medium/high; unnecessarily replaces reusable code. | Borrow patterns within A instead. New orchestration code needed for persistence does not justify discarding the current decision engine. |

Licenses: [Agents SDK](https://github.com/openai/openai-agents-python/blob/main/LICENSE), [PydanticAI](https://github.com/pydantic/pydantic-ai/blob/main/LICENSE), and [LangGraph](https://github.com/langchain-ai/langgraph/blob/main/LICENSE) use MIT; substantial copied/adapted code requires preserving copyright and permission notices. [smolagents](https://github.com/huggingface/smolagents/blob/main/LICENSE) uses Apache-2.0: preserve the license and applicable notices, mark modifications, include applicable upstream NOTICE attribution if distributed, and observe its patent provisions. Direct dependencies also need applicable distribution/transitive notice handling. Independent implementation of general patterns is selected. Record any future copied snippets and exact revision in `THIRD_PARTY_NOTICES.md`; do not copy framework internals casually.

## 4. Final components and ownership

```text
UI / voice adapters → InteractionCore.handle (compatibility)
 → AgentRuntime.handle / resume
      RegistryDrivenAgent.next_decision ↔ persisted transcript
      task lifecycle, event inbox, version/lease, ApprovalService
 → ExecutionPipeline (the trusted gateway)
      validate → policy → admit/journal → MCP → verify
 → existing MCP registry / stdio / RestAdapter
 → existing domain backend
      medical: authenticated MedicalStore.book_with_authorization
 ↔ shared local SQLite authority + narrow medical transaction store
 → verified observation → runtime → DeliveryOrchestrator → UI
```

The SQLite module is a library, not a service. SQL write transactions never surround a model or HTTP call. No model access to SQL, arbitrary URLs, arbitrary code, credentials, approval state mutation or raw MCP context.

Initial medical planner allowlist is exactly `medical.list_departments`, `medical.list_department_doctors`, `medical.search_registration_slots`, `medical.create_registration`, `medical.list_appointment_services`, `medical.search_appointment_slots`, `medical.create_appointment`, `medical.get_my_appointments`, `medical.get_appointment`, `medical.get_task_status`. Runtime-only reconciliation additionally uses `medical.get_operation`. Task type remains `medical_appointment` for wire compatibility; persisted `facts.flow_kind` is `registration|examination|query`, determined from selected tool/capability, not guessed by the frontend. Existing read-only cash workflow remains pinned fallback until its agent-read parity is implemented. Unsupported mutation tools are absent from model projection and denied even if named directly.

| Existing / proposed component | Disposition | Exact final responsibility / migration |
|---|---|---|
| `middleware/server.py`, `MiddlewareApplication`, HTTP handler | KEEP / MODIFY | Keep stdlib HTTP; compose runtime/store/pipeline; derive principal; map typed errors; add state read. |
| `middleware/interaction_core.py`, `InteractionCore.handle` | MODIFY | Thin adapter to `AgentRuntime.handle`; retain route and modality seam. Remove its duplicate load/save/workflow ownership only after regression. |
| `middleware/agent.py`, `RegistryDrivenAgent`, `parse_agent_decision`, `project_registry_tools` | MODIFY | Decide one next action, preserve call IDs, close schemas, project policy-allowed inputs; no execution or approval ownership. Existing `run` becomes a temporary test/legacy wrapper, then REMOVE. |
| `middleware/runtime.py`, `AgentRuntime` | ADD | Single orchestration owner: intake, transcript, lifecycle, bounded driver, proposal creation, resume/reconciliation and canonical results. Not a second orchestrator. |
| `middleware/task_manager/manager.py`, `TaskManager` | MERGE then REMOVE class | Move lifecycle/recovery responsibilities into runtime; do not keep legacy `task_state` and canonical `task.status` as competing authorities. |
| `task_manager/transitions.py`, `contracts.py`, `recovery.py`, `interpreter.py` | MODIFY / KEEP | Pure transition invariants, typed records, recovery descriptions; LLM recovery advice remains nonauthoritative. |
| `middleware/session.py`, `SessionStore`, `SessionState` | MODIFY / MERGE | Durable session/task binding in store; legacy presentation snapshots only during migration. No mutable object is the authority. |
| `middleware/task_store.py`, `SQLiteTaskStore` | ADD | Transactional tasks, proposals, events, issued actions, operation ledger, inbox, leases; migrations and CAS. |
| `middleware/approval.py`, `ApprovalGate`, `ApprovalClassifier` | MODIFY / REMOVE | Replace gate with `ApprovalService` using exact server-issued decisions. Remove classifier as an authorizer; optional language hint cannot grant permission. |
| `middleware/contracts.py`, `PendingToolProposal`, `ToolCall`, `ToolExecutionResult` | MODIFY / KEEP | Keep transport/tool values; replace isolated proposal with durable bound record; add execution request/observation. |
| `middleware/execution.py`, `ExecutionPipeline`, `McpExecutionStage` | KEEP / MODIFY | Existing continuation pipeline is the gateway. Add schema/policy, admission/journal and result-verification stages; one terminal MCP path. |
| `ContextualExecutionPipeline` | MERGE / REMOVE wrapper | Context construction moves into trusted pipeline stages; no separate dispatch route. |
| `DirectMcpExecutionStage` | KEEP test-only | No production selection or bypass; same policy in integration tests. |
| `middleware/medical_workflow.py`, `MedicalWorkflow` | MODIFY then REMOVE orchestration | Keep fallback until parity. Extract domain selection/result checks/receipt projection into `middleware/medical_policy.py`; legacy medical writes must use same authority path before secure rollout. |
| `middleware/cash_sharing_workflow.py` | KEEP during rollout | Read-only fallback; eventually policy-driven agent reads with same canonical projections. |
| `middleware/controller.py`, `InteractionController` | KEEP isolated / later REMOVE | Legacy diagnostics/elderly support only; no canonical medical execution. Disable legacy mutation diagnostics outside explicit local developer mode. |
| `interaction_contracts.py`, `EventEnvelope`, `CanonicalInteractionResult` | KEEP / MODIFY | Preserve envelope and result keys; additive metadata inside server-issued events. |
| `interaction_delivery.py`, `DeliveryOrchestrator`, `WorkspaceProjector`, `ResponseComposer` | KEEP / MODIFY | Deterministic confirmation/receipt and generic processing/reconciliation projection. No invented completion from model text. |
| `interaction_voice.py`, `CoreVoiceTurnProvider`; `voice_transport.py` | KEEP / MODIFY | Same runtime via core; voice text cannot silently approve. Preserve multipart protocol and speech delivery. |
| `voice_services.py`, `RegistryVoiceTurnProvider` | REMOVE after parity | Duplicate dormant agent/approval session path; never activate as-is. STT/TTS adapters stay. |
| `llm_transport.py`, `ChatCompletionClient` | KEEP / MODIFY | Existing provider seam; support full message transcript and single-call options, timeout/error handling. |
| `MCP/registry.py`, `ToolRegistry` | KEEP / MODIFY | Fixed catalog; add operation lookup; add approved-operation transport context; full input validation and ID quoting. |
| `MCP/server.py`, `MCP/rest_adapter.py`, `MCP/models.py`, `middleware/mcp_client.py` | KEEP / MODIFY | Existing MCP/REST dispatch; forward allowlisted trusted operation context, preserve structured errors. |
| `mock_backends/medical/service.py`, `MedicalService`; `backend.py` | KEEP / MODIFY | Reuse domain validation/routes; authenticate service caller and invoke atomic medical unit of work. |
| `mock_backends/medical/store.py`, `MedicalStore`; `database/ponte_store.py` | ADD | Shared schema/connection helper; medical booking unit of work. Library modules, not extra runtime services. |
| Other backend APIs / registry tools | KEEP, restricted | Current registry has 21 tools; welfare referral routes exist but are not registered. New runtime exposes allowlisted reads and hardened medical writes only. R0 is not automatically permission to read any user's data. |

## 5. Interfaces and persisted records

Names in this section are the **planned final interfaces**, not implemented APIs. Use frozen dataclasses / typed enums, JSON-safe values, and schema version `1`. Put runtime records in `task_manager/contracts.py`, transport values in `contracts.py`, and SQL connection/schema helpers in `database/ponte_store.py`. Reuse `sqlite3`; use `jsonschema` 4.x with the exact patch pinned in the implementation dependency manifest and container install. Do not write a partial JSON Schema validator.

```python
class RegistryDrivenAgent:
    def next_decision(self, messages: Sequence[Mapping[str, Any]], *,
                      tools: Sequence[Mapping[str, Any]]) -> AgentDecision: ...
# AgentDecision: action=respond|clarify|tool_call; message?, tool_name?,
# arguments?, tool_call_id?. Native call ID preserved; server generates one for JSON mode.

class AgentRuntime:
    def handle(self, envelope: EventEnvelope, *, principal: Principal
               ) -> CanonicalInteractionResult: ...
    def resume(self, task_id: str, *, principal: Principal
               ) -> CanonicalInteractionResult: ...
    def tick(self, *, limit: int = 10) -> int: ...  # bounded recovery/inbox work

class InteractionCore:
    def handle(self, envelope: EventEnvelope, *, principal: Principal
               ) -> CanonicalInteractionResult: ...  # delegates, owns no task state

class SQLiteTaskStore:
    def ingest(self, envelope: EventEnvelope, principal: Principal) -> IntakeResult: ...
    def load(self, task_id: str, principal: Principal) -> TaskSnapshot: ...
    def claim_turn(self, task_id: str, *, expected_version: int,
                   owner: str, lease_seconds: int = 30) -> TurnLease | None: ...
    def commit_decision(self, lease: TurnLease, *, expected_version: int,
                        decision: AgentDecision) -> CommitResult: ...
    def snapshot(self, session_id: str, principal: Principal
                 ) -> CanonicalInteractionResult: ...
# Each mutation uses an explicit UnitOfWork context, one BEGIN IMMEDIATE / commit.

class ApprovalService:
    def propose(self, uow: UnitOfWork, snapshot: TaskSnapshot,
                call: ToolCall, principal: Principal, *, now: datetime,
                ttl_seconds: int = 300) -> Proposal: ...
    def decide(self, uow: UnitOfWork, decision: ConfirmationDecision,
               principal: Principal, *, now: datetime) -> ApprovalOutcome: ...

class ExecutionPipeline:
    def dispatch(self, request: ExecutionRequest) -> ExecutionObservation: ...
class ExecutionStage(Protocol):
    def handle(self, request: ExecutionRequest,
               next_stage: Callable[[ExecutionRequest], ExecutionObservation]
               ) -> ExecutionObservation: ...

class MedicalStore:
    def book_with_authorization(self, *, operation_id: str,
                                patient_id: str, payload: Mapping[str, Any],
                                idempotency_key: str, caller: ServicePrincipal,
                                now: datetime) -> BackendResponse: ...
    def get_operation(self, *, operation_id: str, patient_id: str,
                      caller: ServicePrincipal) -> Mapping[str, Any]: ...
```

`ExecutionRequest` contains `{task_id, intent_revision, task_version, tool_call_id, tool_name, input, principal, operation_id?}`. It is constructed inside trusted runtime code; the client/model never supplies `Principal` or operative context. For mutations, `input` is loaded from the persisted operation and compared with the request, not trusted from a fresh model decision. R0 reads get a persisted call/event and principal-policy check but no approval or idempotency operation. `ExecutionObservation` contains `{tool_call_id, outcome: observed|succeeded|rejected|unknown, safe_data?, error_code?, request_id, operation_id?, verified: bool}`. `observed` describes a read, not a committed transaction. Existing `ToolExecutionResult` remains the raw transport result inside the pipeline. Network/invalid-body errors on writes become `unknown`, unless there is authenticated evidence of no effect.

Final pipeline order: `InputPolicyStage → AuthorizationJournalStage → ResultVerificationStage → McpExecutionStage`. Verification is an outer continuation stage: it validates the terminal result on return. `McpExecutionStage` builds the existing `ToolCall` context/input envelope from trusted execution context. All callers, including fallback writes and diagnostics, must enter this pipeline; a temporary migration wrapper is removed at cutover.

### Data ownership

| Record | Required fields / invariants | Owner |
|---|---|---|
| Principal / session | `principal_id`, configured patient mapping, session ID, credential binding; routing ID is not identity. | HTTP adapter derives identity; store binds sessions. |
| Session projection revision | Monotonic `session_revision` incremented whenever visible task binding/state changes, including a new linked task. | Store; frontend orders delivery snapshots by session revision, not across unrelated task versions. |
| Task | ID, owner, session, type, engine pinned at creation, status, `version`, `intent_revision`, intent/facts JSON, active proposal/operation IDs, schema version, timestamps. | Runtime. `version` increments each mutation; intent revision changes only accepted effective intent changes. |
| Transcript item | Task ID, monotonic sequence, role, content or structured tool calls/result, call ID, turn/generation, model/prompt version. | Runtime. No hidden chain-of-thought storage required. |
| Proposal | ID, task/owner/patient, intent revision, tool/call ID, immutable final input JSON, canonical SHA256 digest, risk/policy version, display snapshot, created/expiry UTC, state, decision/action evidence. | ApprovalService; backend consumes approved rows in its transaction. |
| Issued action | Random action ID, owner/task/proposal/intent revision, permitted decision, expiry, use/result reference. | Runtime; reproject stable issued IDs, do not generate new permission on every render. |
| Operation | ID, unique proposal ID, owner/patient/tool/path, immutable input/hash, unique idempotency key, transport state, outcome, backend response, attempt metadata. | Runtime prepares/admit/records transport; backend writes terminal outcome. Neither may overwrite terminal state. |
| Inbox / processed interaction | `(principal_id, interaction_id)` unique, session, canonical event hash, sequence, status, resulting snapshot/version. | Runtime; same ID/different event is 409. Voice `turn_id` maps to stable interaction ID. |
| Turn lease | Task, owner token, fencing generation, expiry, expected version. | Runtime; expired/stale worker cannot commit. |
| Medical mutation reservation | Unique `patient_id`, operation ID, acquired at PREPARED; independent of browser session/task lifetime. | Store/pipeline; release on pre-admission cancellation or backend terminal outcome only. |
| Medical booking / backend Task / receipt | Booking ID, patient, actual slot/start/department, terminal domain status; backend task and receipt reference; capacity occupancy. | Medical backend unit of work. Backend Task is not the agent Task. |

Canonical JSON uses UTF-8 sorted keys, compact separators, rejects duplicate keys/nonfinite numbers and preserves validated JSON values without locale-dependent formatting. `input_hash = SHA256(canonical_json(final_outbound_input))`; it covers the full final REST body, including server-injected patient/consent fields, and is the operation lookup/request comparison hash. `proposal_digest = SHA256(canonical_json({schema_version, owner, patient_id, task_id, intent_revision, tool_name, input, policy_version, display_snapshot, created_at, expires_at}))`; it additionally binds the authorization/display context. Store both separately; neither includes credentials. Hashes detect mismatch; authorization comes from trusted rows and caller authentication, not possession of a hash.

Required SQL constraints: one active task per `(principal,session)`; one PENDING/APPROVED proposal per task; one operation per proposal; unique idempotency key scoped to patient+tool; unique transcript result per call ID; unique processed interaction per principal+interaction ID; unique backend receipt/reference and booking IDs; one medical mutation reservation per patient across **all sessions/tasks**. Acquire the reservation with PREPARED, release it on pre-admission cancellation or the backend terminal commit. A DISPATCHED/UNKNOWN operation keeps the reservation indefinitely while unresolved; creating another session/task cannot obtain a new medical mutation/key. Reads and reconciliation remain permitted. Capacity is checked/consumed under the same medical write transaction; capacity >1 needs an occupancy count, not a blanket unique slot constraint. Patient duplicate active bookings are checked in that transaction. Use foreign keys, `busy_timeout`, WAL on local disk, synchronous durability, and short explicit transactions; each thread gets its own connection.

## 6. Four state domains and transitions

### LLM reasoning state

Server transcript plus prompt/model versions is a reconstructible **working context**. It cannot authorize or establish success. Do not persist provider hidden reasoning. A pending assistant call can remain unresolved while paused, but must be closed before another model invocation. Tool outputs are untrusted observations: do not execute instructions embedded in them or promote them to system messages.

### Authoritative task state

| From | Allowed next states / trigger |
|---|---|
| READY | RUNNING when a fenced turn is claimed; CANCELLED; FAILED; HANDOFF. |
| RUNNING | READY on superseding input/stale turn; AWAITING_INPUT on clarification/budget/protocol error; AWAITING_APPROVAL on durable proposal; EXECUTING only through approved admission; COMPLETED for verified query result; FAILED/HANDOFF. |
| AWAITING_INPUT | READY on valid message/selection/continue; CANCELLED; HANDOFF. |
| AWAITING_APPROVAL | Remains AWAITING_APPROVAL while proposal APPROVED/operation PREPARED; READY on pre-admission intent change/modify/expiry; EXECUTING only on DISPATCHED admission; CANCELLED on pre-admission explicit rejection/cancel; HANDOFF only without unresolved effect. |
| EXECUTING | RECONCILING on uncertain transport/crash; READY on definitive no-effect rejection requiring replan; COMPLETED only on verified receipt; HANDOFF only with known outcome. |
| RECONCILING | COMPLETED on verified committed outcome; READY on terminal no-effect rejection. After automatic retry budget, remain RECONCILING with `recovery.needs_assistance=true`; no new mutation while outcome is unknown. |
| COMPLETED / CANCELLED / FAILED / HANDOFF | Terminal. A new request creates a new task linked to the old task. Human resolution uses an audited new recovery event/task, never silent terminal rewriting. |

`FAILED` and terminal `HANDOFF` require no unresolved external effect. Unknown outcomes remain RECONCILING, including when human assistance is needed; do not abandon their patient-wide reservation. Operator resolution must record verified backend outcome, not merely waive an unknown effect. Terminal task status does not erase records. Read completion requires a valid read observation; booking completion requires a verified domain receipt. Reconciliation work may run without an LLM turn.

### Proposal state

`PENDING → APPROVED | REJECTED | INVALIDATED | EXPIRED`.

`APPROVED → CONSUMED | INVALIDATED | EXPIRED` **only while its operation is PREPARED**, except backend consumption/rejection during admitted execution. Once DISPATCHED/UNKNOWN, runtime cannot invalidate/rewrite the frozen intent; backend either consumes for a terminal booking/rejection or rejects an expired unconsumed grant. Backend expiry makes the proposal EXPIRED with terminal no-effect operation rejection. A consumed proposal never returns to PENDING. Invalidated/rejected/expired proposals are immutable audit rows. A replacement is a new ID and requires a new explicit decision.

Backend `CONSUMED` means the authorized operation has a durable terminal result, possibly a business rejection; it does not alone mean success. If expiry occurs after a successful commit, replay returns the already committed receipt rather than denying visibility of the outcome. Sequential or concurrent duplicate approval resolves to the original operation/snapshot. The same owner/action/decision repeat may retrieve that existing operation/receipt after TTL; it cannot authorize a fresh dispatch. A stale/foreign action or changed decision fails; never reinterpret a duplicate approve as a new authorization.

### External operation / transport state

Keep independent columns:

* Transport: `PREPARED → DISPATCHED → ACKNOWLEDGED | UNKNOWN`; `UNKNOWN → DISPATCHED` only for a verified safe same-key resend; `PREPARED → CANCELLED` before admission. Attempt rows distinguish repeated transmissions. A terminal backend outcome takes precedence over transport flags.
* Backend outcome: `NOT_APPLIED → SUCCEEDED | REJECTED`. `NOT_APPLIED` means no committed backend effect **at the lookup instant**, not proof that a previously sent request cannot arrive later. `SUCCEEDED/REJECTED` are immutable and include the replay response. PREPARED cancellation forbids future admission; an admitted operation cannot be cancelled by a timeout handler.

No destructive resubmission with a new key after UNKNOWN. Retry of the same admitted operation is allowed only with the same payload/key and backend atomic deduplication. For future APIs lacking this contract or exact status lookup, remain unresolved and hand off; duplicate avoidance trades availability for safety.

## 7. Minimal execution lifecycle and concurrency

1. Derive `Principal` outside model/client data. Validate envelope and bind session to principal. `ingest` atomically deduplicates interaction ID, records event and selects/creates task. An accepted new utterance before admission conservatively invalidates any PENDING/APPROVED proposal, cancels PREPARED operation if present, increments intent revision and fences old model work. Even “yes” text requests a fresh explicit confirmation; natural language alone is never the approval credential in this release.
2. Close the pending assistant call with `SUPERSEDED`, `DENIED` or `EXPIRED` as applicable, **then** append the new user message to model-visible history. Inbox arrival time is audit evidence; transcript order must remain protocol-valid. An approval event is not a new user prompt inserted in the middle of a tool exchange.
3. Claim a short persistent turn lease; read snapshot/version; commit transaction. Reconstruct system prompt plus ordered persisted messages and all closed call/result pairs. Do not accept client-supplied history. Compact only complete historical exchanges; retain current intent and verified facts with provenance, and keep the full audit transcript in storage.
4. Call model outside transactions. Permit exactly one tool call per decision (`parallel_tool_calls=false` where supported). Preserve native ID or generate one for strict JSON mode. Reject an entire multiple-call response before dispatch; do not execute its first call opportunistically. Use a bounded protocol correction, then AWAITING_INPUT.
5. CAS-commit the decision under expected version and lease generation. If a message arrived meanwhile, discard stale model output, including proposed tool arguments. A read result returned late may be recorded as an audit observation, but cannot advance newer task state.
6. Validate tool against the policy allowlist and JSON Schema. Runtime fills patient/consent/context fields; model schema omits trusted fields. Reject unknown fields, types/enums, invalid IDs/date constraints, unsupported risk and permission mismatches. Select a returned slot satisfying task constraints; do not trust a model-invented slot ID.
7. R0 reads execute through pipeline, persist assistant call plus safe result with exact ID, then continue. R1/R2 actions produce an immutable proposal and issued approve/reject/modify actions. Persist before returning AWAITING_APPROVAL; no booking call happens at proposal creation.
8. Explicit approval enters a SQL transaction: verify principal/session/task/action/proposal/current intent/digest/expiry/policy and absence of another medical mutation reservation for this patient, move PENDING→APPROVED, create unique operation PREPARED and its permanent random key, acquire the reservation. Duplicate input returns existing operation, never creates another. The original assistant call remains open until the authorized tool resolves.
9. Pipeline admission atomically rechecks bindings and CASes PREPARED→DISPATCHED with task EXECUTING. Persist exact input, hash, principal, proposal/call IDs, policy, key and attempt ID **before sending**. This transaction and intent-edit ingestion compete for one SQLite write lock. Winner defines order. After admission, append later user changes to the inbox but do not advance effective intent revision; tell the user submission is underway and outcome is being checked.
10. MCP sends only the stored operation with server context. Backend authenticates caller and atomically validates the current frozen task revision and approved operation; checks capacity/date/patient/domain constraints; consumes approval; writes booking/backend Task/receipt/replay outcome. No remote call occurs inside this SQL unit of work.
11. Pipeline verifies receipt against operation, persists observation and closes the exact assistant call. Runtime reports success from verified facts. If model wording fails, deterministic receipt response still works. Process queued changes only after closing the operation: a successful booking is disclosed before any new change request; automatic cancellation/rescheduling is forbidden without a separately supported approved tool.
12. Model loop defaults to eight decisions and a 20-second driver budget per user/approval turn; model transport timeout remains separately bounded. Stop before the next call when budget is exhausted, persist AWAITING_INPUT with `continue_task` server action. Never convert the step cap into success. Repeated explicit continues share a 32-decision task ceiling, then HANDOFF only if no operation is unresolved. Reconciliation has its own bounded attempts (1, 2, 4, 8, 16 seconds, then needs assistance while still RECONCILING) and does not spend model steps.

Use an application-owned bounded thread pool to drive tasks; no separate scheduler service. `AgentRuntime.tick` scans persisted ready inbox/expired leases/reconciliation work on startup and every second. Only lease/CAS permits committing model work. HTTP attempts a bounded synchronous drive; if busy/budgeted, returns current canonical snapshot. A GET snapshot endpoint and small frontend polling change handle progress/restart. A browser fetch abort is not cancellation; only persisted cancel/intent events can change task authority. On shutdown stop intake, finish short SQL writes, and leave admitted operations for recovery; never erase them.

## 8. Trust boundary, backend validation and result rules

The UI and model are untrusted. The middleware's principal mapping, task store, policy and pipeline are trusted. MCP transport is not authorization; fixed names do not imply safe access. Backend must independently enforce the authorized operation. SQLite file access is available only to the service processes; sharing it is a deliberate same-host trusted computing boundary.

For this demo, use a server-issued HttpOnly SameSite session cookie bound to a **configured demo principal** and a configured service credential validated by the backend. Bootstrap the cookie through an additive `/api/session` endpoint (POST, same-origin/allowlisted origin), without replacing the UI flow. The browser's local session ID remains routing only. Require origin/CSRF checks on state-changing cookie requests; development cross-origin client requests use `credentials: include` and explicit allowed origins. This provides a server-bound demo identity, not proof of the physical speaker or real patient identity. Real patient deployment remains blocked on actual authentication/delegation design; OAuth migration is not part of this refactor. Shared-device sessions cannot provide nonrepudiation.

Add trusted context `operation_id` mapping to `X-Ponte-Operation-Id` for hardened medical writes. `idempotency_key` retains its existing `Idempotency-Key` mapping. Extend `CONTEXT_PROPERTIES`, `ToolContext` allowlist and `ContextRequirements`; only server code can create these values. The model sees neither. Approval proof is the server-owned proposal/operation row, not the header alone. Backend checks credential, patient mapping, operation/proposal ownership, exact method/tool/input hash/key, task's frozen intent revision and executing/reconciling state, unexpired APPROVED proposal, and admitted transport state.

Backend transaction procedure:

1. Begin immediate; authenticate service credential and patient scope. Load operation by ID.
2. Verify request key and canonical input against stored immutable values. A same key/different input is `IDEMPOTENCY_CONFLICT` (409). Never return another patient's receipt.
3. If operation already terminal, return its stored original success/rejection response to the authorized caller, even after proposal expiry. Do not book again.
4. Otherwise validate current task/proposal/admission bindings and expiry. Business validation failures are durable REJECTED/no-effect results; consume the attempted proposal (or EXPIRED for expiry). Invalid unauthorized requests cannot consume another owner's operation.
5. Within this transaction recheck slot/date window/capacity/duplicate patient booking; atomically store all business records and SUCCEEDED response and consume proposal. Crash before commit rolls back all writes; crash after commit leaves the replayable outcome.

Do not hold model/HTTP I/O inside this transaction. ID generation must use SQL-backed counters/random unique IDs, not separately persisted JSON counters. Booking data migration includes existing medical records and backend tasks with stable IDs. Legacy idempotency responses are imported as immutable legacy replay records; they cannot be reinterpreted as approved new operations.

Result verification for registration requires `data.resourceType == "Appointment"`, `status == "booked"`, nonempty ID, matching patient, department, selected slot and timezone-aware start/end/location, completed backend task referring to that appointment, matching operation ID, and nonempty receipt reference/valid issued time. Use approved server slot snapshot and operation hash. Examination `medical.create_appointment` legitimately uses `confirmed`; validators are tool-specific. Strengthen reusable receipt helpers; never require the word `confirmed` for an outpatient registration. Any mismatch is `RESULT_UNVERIFIED`, no success UI, reconcile using exact operation. Transport `ok=True` alone is insufficient.

Tool errors feed the model as structured safe observations (`SLOT_NOT_AVAILABLE`, `APPROVAL_EXPIRED`, `SUPERSEDED`, `RESULT_UNVERIFIED`, etc.). Redact credentials, stack traces and unnecessary medical data. Backend lookup/reconciliation evidence outranks model speculation. Policy/user errors return typed recovery and no execution; transient read errors can retry within budget. Unknown write outcome is not labeled failed or blindly retryable. HTTP validation errors are 400, owner-denied 403/404 without data leakage, stale/reused conflicting event/action 409, expired decision 410; domain rejection/processing is represented in the canonical response. Duplicate valid approval is 200 with existing operation state/receipt. Unexpected failures have correlation IDs and no raw secrets.

The existing `McpStdioClient.call_tool` serializes requests under its lock ([mcp_client.py:283](../../middleware/mcp_client.py#L283)); retain that behavior. After timeout/protocol desynchronization, recycle the MCP child before another RPC so a late response cannot be mistaken for a new call. Recycling transport does not cancel a backend transaction. Classify the admitted operation as unknown and reconcile; use the same operation/key if safe to resend.

## 9. Exact tools and mandatory scenario

**General cardiology consultation uses `medical.create_registration`.** `medical.create_appointment` exists but serves examination/treatment appointments. The current catalog includes ultrasound, physiotherapy and cardiac ultrasound, with referral constraints. Do not fabricate `medical.create_appointment()` as a generic visit tool or fabricate a referral.

Current schemas from [registry.py:289](../../MCP/registry.py#L289):

| Tool | Current `input` (required in bold) | Backend route |
|---|---|---|
| `medical.list_departments` | `keyword?:string`, `location_id?:string`, `active_only?:boolean` | GET `/mock/medical/v1/departments` |
| `medical.search_registration_slots` | **`department_id:string`, `date:string`**; `doctor_id?:string`, `session?:"morning"|"afternoon"`, `location_id?:string` | GET `/mock/medical/v1/registration-slots` |
| `medical.create_registration` | **`patient_id:string`, `department_id:string`, `slot_id:string`, `consent:boolean`**; `doctor_id?:string`, `visit_reason?:string`, `notes?:string` | POST `/mock/medical/v1/registrations` |
| `medical.get_appointment` | **`appointment_id:string`** | GET `/mock/medical/v1/appointments/{appointmentId}` |
| `medical.get_task_status` | **`task_id:string`** | GET `/mock/medical/v1/tasks/{taskId}` |

All use `{context,input}`. Medical context requires server `authorization`/locale; patient tools additionally patient context, writes additionally idempotency key. Current schema says consent is boolean; backend requires literal true. Planned policy projection hides patient/consent from the model, fills server patient and the authorized outbound consent value, and closes extra input properties. The proposal includes the exact intended final body; setting a planned consent field is not evidence of approval.

### Required new lookup contract

Add exactly one medical tool, **`medical.get_operation`**, R0, GET `/mock/medical/v1/operations/{operationId}`. Existing appointment detail omits slot ID and receipt and requires a known booking ID, so it cannot reliably reconcile an unknown create result.

```json
{
  "type": "object", "additionalProperties": false,
  "required": ["context", "input"],
  "properties": {
    "context": {
      "type": "object", "additionalProperties": false,
      "required": ["patient_id", "authorization"],
      "properties": {
        "patient_id": {"type": "string", "minLength": 1},
        "authorization": {"type": "string", "minLength": 1},
        "accept_language": {"enum": ["zh-TW", "en-US"]},
        "request_id": {"type": "string", "minLength": 1}
      }
    },
    "input": {
      "type": "object", "additionalProperties": false,
      "required": ["operation_id"],
      "properties": {"operation_id": {"type": "string", "minLength": 1}}
    }
  }
}
```

Response: `{request_id, data:{operation_id, tool_name, input_hash, outcome:"NOT_APPLIED"|"SUCCEEDED"|"REJECTED", result:null|<original success body>, error:null|{code,message}}}`. Known nonterminal admitted operation returns NOT_APPLIED and null result/error; this is an instantaneous observation and safe same-key retry requires the atomic backend contract. Unknown ID or wrong patient returns 404; no fabricated no-effect assertion. Rejected operation returns stable error and no result. SUCCEEDED includes the original `{request_id,data,task,receipt,operation_id}` success body, enabling complete correlation. Add `operation_id` to hardened booking success/rejection envelopes; existing fields stay compatible. The lookup is primarily runtime reconciliation, not a model-selected way to read arbitrary IDs; enforce owner policy.

### Primary acceptance trace

Freeze service clock at `2026-10-13T09:00:00+08:00`; resolve “next Tuesday” to **2026-10-20** in `Asia/Macau` (same offset as client timezone, service locale is authoritative for appointment dates). Add deterministic registration fixtures `SLOT-REG-20261020-CARDIO-1400` and `SLOT-REG-20261020-CARDIO-1530`, both DEPT-CARDIO/DOC-002/LOC-MAIN-OPD, free with capacity. These IDs/data are **planned test fixtures**, not current availability: existing registration fixtures are fixed August 12 and have no 15:30 slot. Extend rolling outpatient demo seed separately after deterministic tests.

| Step | Model / execution | Persisted authoritative consequence |
|---|---|---|
| 1 | User requests cardiology next Tuesday afternoon. | Task T, effective intent revision 1; user message stored. |
| 2 | `medical.list_departments`, input `{"keyword":"Cardiology","active_only":true}`. | Valid read returns DEPT-CARDIO; assistant call/result paired. |
| 3 | `medical.search_registration_slots`, input `{"department_id":"DEPT-CARDIO","date":"2026-10-20","session":"afternoon"}`. | Returns 14:00 and 15:30; exact server snapshots stored with provenance. |
| 4–6 | Model selects 14:00 via `medical.create_registration` intent, model inputs department/slot; runtime builds proposal body. | P1 PENDING binds T/revision1 and frozen final body, display cardiology/date/time/location; assistant mutation call C1 remains open. AWAITING_APPROVAL. **Zero booking requests.** |
| 7–8 | “Actually, make it after 3 PM.” | Atomic intake invalidates P1, closes C1 with `SUPERSEDED`, appends new user message, advances intent revision2 and fences old work. |
| 9 | Model re-evaluates verified slots or repeats `medical.search_registration_slots` with the same schema. | Runtime enforces local `start > 15:00` from timezone-aware returned slots. There is no `after_time` tool parameter. |
| 10 | Model selects 15:30. | P2 PENDING/new call C2, bound to revision2; no booking yet. |
| 11 | User clicks server-issued approve action: `confirmation_decision` with P2/action/task IDs. | Verify action belongs to this principal/proposal, current revision and TTL; P2 APPROVED; O2 PREPARED with stable key K2. |
| 12 | Pipeline CAS admits O2. | O2 DISPATCHED; T EXECUTING/revision2 frozen. State/key/body saved before network send. |
| 13 | `medical.create_registration`, input `{"patient_id":"<server patient>","department_id":"DEPT-CARDIO","doctor_id":"DOC-002","slot_id":"SLOT-REG-20261020-CARDIO-1530","consent":true}`; server context includes O2 and K2. | MCP forwards existing POST contract plus trusted operation header. Backend checks caller, P2, current T revision, exact body/key, expiry and slot capacity in one transaction. |
| 14 | Backend returns Appointment with `status:"booked"`, completed backend Task, receipt `MED-REG-*`, O2. | Atomic booking/receipt/replay outcome SUCCEEDED and P2 CONSUMED. |
| 15 | Pipeline verifies O2 result; C2 tool result closes; model sees verified result. | T COMPLETED; deterministic response/receipt confirms 15:30 on Oct 20. Model may phrase response but cannot weaken verified facts. |

### Failure and race acceptance

| Event | Required behavior |
|---|---|
| Approve invalidated P1 | 409 `STALE_PROPOSAL`; no operation or booking, even if its original digest/action is replayed. |
| Submit P2 approval twice, even with different interaction IDs | One operation per proposal. Return pending operation or same receipt; no second key, no second booking. Same interaction ID/different body is 409. |
| Timeout before/after possible commit | Mark transport UNKNOWN only if outcome still nonterminal using CAS. Query `medical.get_operation(O2)`. SUCCEEDED yields verified receipt; REJECTED yields recovery; NOT_APPLIED permits bounded identical-key resend under hardened contract. No new key. Late timeout cannot overwrite success. |
| Slot disappears after approval | Backend rechecks capacity in its transaction; durable REJECTED `SLOT_NOT_AVAILABLE`; no booking. Close C2 with rejection; re-search and require new proposal/approval. Never silently choose another slot. |
| Restart awaiting approval | Reload task/proposal/transcript and stable actions; PENDING remains usable until UTC expiry. Expired proposal closes call and requires refresh/new approval. No preapproval dispatch. |
| Restart after admission, before send | RECONCILING; exact lookup then same-key recovery as above. Do not infer success or failure from missing HTTP response. |
| Concurrent message and approval | Ordered by SQLite intake/admission transactions. If edit wins before admission, proposal invalid and approval/admission rejected. If admission wins, intent remains frozen; edit queued until outcome known. This is not determined by browser send timestamp. |
| Two model requests / expired lease | Only current fenced version may commit; stale decision/result cannot create proposal or admit operation. |
| Concurrent final-capacity bookings with different keys | Medical unit of work admits capacity once; other operation gets a stable rejection. |
| User opens new session after unresolved timeout/needs-assistance | Patient-wide reservation rejects new medical mutation admission with `OPERATION_UNRESOLVED`; permit reads and recovery of original operation only. No new-key bypass. |
| Database unavailable | Fail closed before admission; after admission report pending/unknown, preserve operation ID, do not dispatch new actions. |

## 10. HTTP compatibility and rollout boundary

Keep `/api/interactions`, `EventEnvelope` routing/event shape, `/api/voice/turn` multipart, speech routes, and response keys `interaction_id`, `task`, `response`, `workspace`, `confirmation`, `recovery`, `receipt`, `speech_audio`. Frontend already forwards opaque server action events; add `intent_revision`, proposal digest and expiry inside these actions/confirmation, binding issued action IDs in storage. Existing `confirmation_id` is the proposal ID on the wire. Old active confirmations are not upgraded into authorization.

Exact agent-mode approval event is `{"type":"confirmation_decision","action_id":"<issued action>","task_id":"T","confirmation_id":"P2","intent_revision":2,"proposal_digest":"<stored digest>","decision":"approve"}` inside the existing `{"routing":{"interaction_id":"<unique client event>","session_id":"<routing session>"},"event":{...},"audit":{}}` envelope. Extend `ConfirmationDecision` with required `intent_revision:int` and `proposal_digest:str` in agent/hardened mode; `decision` remains `approve|reject|modify`. Action records bind each allowed decision. Wire metadata is compared against stored values, never used to rebuild authority. The frontend forwards it unchanged. Legacy-mode old action shapes remain only until their pinned tasks finish; hardened mode rejects missing binding fields and requests a fresh confirmation.

Map runtime states to existing UI statuses: READY/RUNNING→`awaiting_input` with `current_step:"processing"`; AWAITING_INPUT→`awaiting_input`; AWAITING_APPROVAL→`awaiting_confirmation`; EXECUTING→`executing`; RECONCILING/HANDOFF→`needs_recovery`; completed/cancelled/failed to their lowercase equivalents. APPROVED/PREPARED projects processing with no newly executable approve action even though runtime status is still AWAITING_APPROVAL. Extend projector/composer with explicit processing/reconciling views and server text; booking proposal stays `appointment_confirmation`. Keep raw authoritative state as additive `task.runtime_status`, plus `task.version`, `task.intent_revision`, `task.pending_operation_id`, and top-level `session_revision`. The browser must not infer workflow permissions from these fields.

Add GET `/api/interactions/state?session_id=<routing-id>` returning the same delivery envelope, owner checked; optional `task_id` query selects an owned archived task. Use `interaction_id:"snapshot:<task_id>:<version>"` for snapshot reads. Frontend polls at 1 second while processing/executing/reconciling (including APPROVED/PREPARED processing), backs off to 5 seconds on network error, stops in waiting/terminal states, and restores the last owned task after reload. Compare `session_revision` only within the same session to discard stale responses, and task versions only within the same task. A new task version1 must supersede old task version20 when its session revision is newer. Explicit archived-task reads do not replace the active session binding. Add `/api/session` bootstrap as above. These are additive endpoints and a small compatibility client change, not a new frontend. No SSE needed for minimum integration.

Pin `engine=legacy|agent` at task creation, behind `PONTE_RUNTIME_MODE=legacy|agent` (new setting). Never switch an in-flight task between engines. Start with new test/demo sessions; existing in-memory approvals cannot survive cutover and must be cancelled/reconfirmed explicitly. Keep legacy medical flow until agent regressions pass; before enabling hardened writes, adapt fallback medical confirmation to the same proposal/operation/pipeline/backend gate. Legacy raw mutation diagnostics are developer-only and disabled in secure mode. Do not roll back to an old writer against an admitted-operation database; disable new task creation and reconcile before binary rollback.

## 11. Known limitations and rejected alternatives

* Same-host SQLite and mock medical atomic writes are an explicit deployment assumption. Real services require documented idempotency retention, authenticated operation-status lookup and authorization exchange; some cannot support safe automatic retry. No universal exactly-once claim.
* Demo identity is server-bound configuration, not real patient authentication or verified voice identity. No OAuth, identity provider or legal consent system is implemented here.
* New runtime write allowlist initially covers medical registration and the existing examination booking path once adapted. Other R1/R2 tools remain disabled until they satisfy the same backend guarantees. Welfare backend presence does not mean an MCP tool exists.
* No cancellation/rescheduling write is invented. A changed request after commit requires explicit user discussion/new supported approved action; it cannot silently undo a booking.
* Full event sourcing, distributed queues, workflow DSLs, vector memory, multi-agent planning and general browser/code execution add no necessary correctness for this scope.
* Reject deleting `InteractionCore` first, wiring the dormant voice agent, trusting LLM approval confidence, treating consent/digest as authorization, accepting multiple mutation calls, using HTTP abort as cancellation, and reporting success from a text answer or transport status.
* Reject a second gateway abstraction beside `ExecutionPipeline`, a separate TaskManager authority, and uncoordinated SQLite/JSON writes. Shared SQLite is intentionally a narrow medical persistence change, not migration of all backend domains.
* Keep audit/operation records indefinitely for the demo. A real retention/deletion policy needs domain requirements; do not auto-delete idempotency records while retries remain possible. Restrict DB/log access and redact secrets; avoid retaining raw voice audio by default. Encryption/real production privacy compliance is outside the demo guarantee.

Implementation phases and test traceability are defined in [Ponte_Implementation_Plan.md](Ponte_Implementation_Plan.md). Final two-slide views: [system architecture](Ponte_System_Architecture.svg) and [execution sequence](Ponte_Execution_Sequence.svg).
