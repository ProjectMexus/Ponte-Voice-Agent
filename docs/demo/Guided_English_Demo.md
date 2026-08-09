# Guided English medical demo

The guide presents the existing seven-turn cardiology story in English. It works
with both scripted and real model servers and labels the mode explicitly. It
does not replace model decisions, dispatch tools, or create approval events.

## Run

Use the existing startup in [the cardiology runbook](../CARDIOLOGY_DEMO.md), with
`--demo-agent real --medical-data-profile live-demo-v2` for a real model, or
`--demo-agent scripted --medical-data-profile live-demo-v2` for a free rehearsal.
Use a fresh `--data-dir` for each presentation so 15:30 is available. The real mode
requires existing local model credentials and incurs API charges.

Append `&guide=medical` to the frontend URL that already contains `?middleware=…`.
For example, with default ports:
`http://127.0.0.1:5173/?middleware=http://127.0.0.1:8090&guide=medical`.
Alternatively click **Try the 7-step demo**. Entering from an existing conversation
asks to start a new conversation; cancelling preserves it. The guide locks its
display and request locale to English. **Exit guide** preserves the current
conversation, draft and confirmation card, and restores language selection.

## Interaction

1. Book a cardiology appointment next Tuesday afternoon.
2. Only after 3 PM.
3. Wait, do I have any other appointments?
4. Will that clash with my existing appointments?
5. Go back to the appointment we were booking.
6. The 3:30 PM one, please.
7. Review the formal card and click its existing approval button yourself.

**Use this message** fills the composer. Review or edit it, then press Send;
speaking and free text remain available. **Review confirmation** only focuses
the actual server card. The guide never clicks or submits approval.

## Progress and limitations

Progress is local presentation state and resets with a new conversation or page
reload. Each fresh server response can advance at most one step. An additive
`task.facts.demo_observation` (version 1) reports the validated control action and
successful read-tool names for that response only. It is generated from execution
logs on a copied response task, never stored in runtime state or supplied to the
model. It contains no patient identifier, credentials or approval capability.

The browser combines that observation with authoritative task facts: task identity,
intent revision, replaced candidate, the strict after-15:00 constraint, queried
appointment snapshot, grounded conflict result, a successful resume search, an
issued confirmation card, and a matching completed receipt. A draft that expired
while paused may be replaced with a new candidate ID after a successful search,
provided the task, intent revision, constraints and selected slot still match. Assistant wording,
button previews and message count cannot complete a step. Existing clients can
ignore the extra fact; endpoints and service actions are unchanged.

Clarification, unavailable slots, missing evidence, changed tasks, transport
errors and unknown execution outcomes stop progress. Read the response and
clarify/retry when appropriate, exit to continue freely, or start a new
conversation. An expired approval may need a new card outside this fixed route.
The guide does not silently replace a missing 15:30 slot or mark an off-route
booking as a successful demo. Starting over does not undo submitted bookings.

This is a fixed demonstration route, not an assessment of unrestricted agent
capability. It deliberately requires the original 14:00 draft and the revised
15:30 draft. The existing eight evaluation cases and original pilot evidence are
unchanged.

## Verification

`node --test tests/frontend_*.test.mjs` covers the guide and existing UI flows.
`python -m unittest tests.test_guided_demo_e2e tests.test_english_medical_demo_e2e tests.test_frontend_interaction_contract`
checks read-only progress evidence and real HTTP/MCP execution with scripted
model decisions. Paid model rehearsals remain separate from these regressions.


### Local validation — 2026-10-14

- 72 frontend tests passed, including preview-only messages, English locale,
  reset/cancel, stale evidence, failed reads, unknown outcomes and draft refresh.
- 24 guided/English/multi-turn/HTTP contract tests passed.
- 46 workflow, model and delivery regression tests passed.
- Browser rehearsals completed all seven steps separately with the scripted
  client and the configured real `gpt-4.1-mini` model. Both reached a verified
  2026-10-20 15:30 receipt after a manual test click on the actual approval card.
  The real rehearsal is one observed path, not a reliability estimate.
- An earlier real rehearsal was interrupted by a long tool-permission review
  timeout. On resume, an expired draft was correctly renewed by the runtime;
  the guide originally stopped on the new candidate ID. The same-slot refresh
  check and its two regression cases were added before the successful full run.

The original pilot files, eight evaluation cases and the main checkout were not
modified. Test bookings used separate synthetic data directories. Screenshots
and service logs are local validation artifacts, not user data or provider keys.
