# Cardiology integration results — 2026-10-14

The seven-turn cardiology workflow is restored alongside main's existing UI and general agent. The accepted runtime revision is `e8f88b4b6011a83987c2bb3810cf3526038ad59c`. The final eight-case evaluation and English rehearsal ran against this committed runtime; later documentation/evidence commits do not change it.

## Outcome

| Track | Task completion | State consistency | Unsafe executions | Checkpoints observed |
| --- | --- | --- | --- | --- |
| Scripted regression | 8/8 | 47/47 | 0 | 47/47 |
| Real model | 8/8 | 46/47 | 0 | 47/47 |

The requested model was `gpt-4.1-mini`, using the configured OpenAI-compatible chat-completions endpoint at temperature 0. Every case had isolated data and a fresh session/process. These are single attempts on eight fixed paths, not a production reliability estimate.

The remaining real-model state failure is MT04 checkpoint 3: an unspecified interruption should have prompted clarification, but the model queried appointments directly. The scenario subsequently completed. This is a conversational interpretation failure; no unauthorized write occurred. It remains failed in SCR and was not manually upgraded.

[Final full report](../outputs/evaluation/integration-acceptance-20261014-131931/report.md) · [Structured results](../outputs/evaluation/integration-acceptance-20261014-131931/results.json) · [Runtime/model metadata](../outputs/evaluation/integration-acceptance-20261014-131931/metadata.json)

## Before and after

| Recorded run | Scripted TCR / SCR / UEC | Real TCR / SCR / UEC |
| --- | --- | --- |
| First pilot | 5/8 · 36/47 · 0 | 3/8 · 30/47 · 0 |
| Earlier repaired demo branch | 8/8 · 47/47 · 0 | 6/8 · 44/47 · 0 |
| Final integrated runtime | 8/8 · 47/47 · 0 | 8/8 · 46/47 · 0 |

Sources: [first pilot](../outputs/evaluation/multi_turn/first-full-16/report.md), [earlier scripted](../outputs/evaluation/multi_turn/post-fix-final-scripted/report.md), [earlier real model](../outputs/evaluation/multi_turn/post-fix-final-real/report.md). These are recorded runs, not a controlled statistical comparison; model variability and evaluator/source versions must be considered using their metadata.

The frozen dataset retains its original SHA256, `e2afda1cbf7cea882dd44adfce03c2d8e31a2b8ff62847b5d724d7e20fe39100`. All 970 previously tracked historical evidence files were restored and verified against their original Git blob IDs. `.gitattributes` prevents Windows newline rewriting of evidence and the frozen dataset. No original report, trace, backend record, case or oracle was overwritten to improve scores.

## English and UI evidence

- [Final real-model English rehearsal](../outputs/evaluation/integration-english-real_model-20261014T052159Z/evidence.json): the original seven-turn assertions passed, including strict after-15:00 constraints, appointment snapshot retention, conflict answer, fresh availability on resume, formal approval, verified 15:30 receipt and replay. Exactly one write dispatch and one backend booking request occurred. Backend records are retained beside the evidence.
- [Scripted English rehearsal](../outputs/evaluation/integration-english-scripted-20261014T032011Z/evidence.json): same seven-turn assertions and one write.
- Main's actual frontend was exercised through the browser in English: draft P1 14:00, revised P2 15:30, inquiry, conflict answer, resume, selection, approval, and receipt `MED-REG-0001`. The isolated browser demo used scripted decisions and actual HTTP/MCP/backend execution. It was not counted as a real-model run.
- Main's frontend source is unchanged. A local receipt screenshot is retained at `.tmp/integrated-english-ui.png`; it is a browser check, not hardware microphone or cloud speech validation.

## Changes made

1. Restore `DemoMedicalWorkflow`, its time/reference parser and model adapter. Route enabled cardiology requests under `SessionStore.transaction`; keep active task ownership and preserve the general `AgentOrchestrator` for other services.
2. Restore the opt-in `live-demo-v2` catalogue and synthetic history. Retain main's rolling legacy inventory and its persisted bookings. Add process-local backend write locking; do not claim crash-atomic JSON storage.
3. Integrate domain draft/confirmation/receipt projections with main's bilingual delivery and operation replay. Exact server-issued action payloads remain unchanged.
4. Reject model constraint updates that contradict explicit parsed boundaries, with one correction opportunity. Clarify query-versus-answer semantics in the existing control prompt.
5. Permit selecting a current published option when no automatic draft exists. Resolve the presented reference, refresh availability, create a bound proposal, and query prerequisites before showing a formal card. Selection without published options cannot issue confirmation. Approval remains a separate event.
6. Restore explicit launcher/profile switches and supplementary domain diagrams. Add a reproducible English acceptance command; keep evaluation artifacts out of container build context.

## Local regression checks

| Check | Result |
| --- | --- |
| Middleware discovery, final runtime | 290 tests passed |
| Integration discovery, final runtime | 189 tests passed |
| MCP discovery | 21 tests passed |
| Frontend Node behavior tests | 59 tests passed |
| Evaluation scoring/observer tests | 32 tests passed |
| Original medical inventory and opt-in profile | 39 tests passed (overlaps integration discovery) |
| Targeted explicit-time and option-selection regressions | 16 tests passed (overlaps middleware discovery) |
| Python compilation | Passed |
| Documentation links and supplementary SVG XML | Passed |

The counts are per command and should not be summed as unique tests. No cloud deployment or full container build was performed. Credential values were not saved in new evidence or committed; only synthetic medical data was used.

## Attempts retained during integration

- `integration-seven-turn-20261014-105918`: failed pre-final integration run. A fixed-clock fixture callable rejected a new keyword argument; slot queries failed. This was a compatibility defect, not evidence of deficient medical data or model capacity.
- `integration-calibration-final`: MT01/MT07 calibration after fixing that fixture compatibility; 12/12 checkpoints passed. Subset calibration is not a full benchmark score.
- `integration-final-20261014-110350`: pre-boundary-fix scripted 8/8 and real 5/8, retained unchanged.
- Earlier English real attempts are retained separately: incorrect inclusive boundary; safe clarification after correction exhaustion; and a snapshot-refresh mismatch against the original retention assertion. The original assertion was retained, and the later prompt clarified answering from the retrieved snapshot.
- `integration-release-20261014-111955`: scripted 8/8 and real 7/8, before the no-draft option-selection fix. Its failure led to the state-transition correction; it is not replaced by the targeted pass.
- `integration-option-selection-recheck`: MT03 passed in both tracks after the correction. The final headline above comes from a fresh full eight-case run, not from combining successful subsets.

Startup and dialogue scripts: [CARDIOLOGY_DEMO.md](CARDIOLOGY_DEMO.md). Session/approval state remains process-local; distributed durability, production identity and cloud speech accuracy remain outside this demo's validation.
