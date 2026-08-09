# English medical demo

The seven-turn workflow is now integrated with main's current UI and general agent. Use the [current runbook](../CARDIOLOGY_DEMO.md) for startup and routing. The real-model integration rehearsal at [20261014T031039Z](../../outputs/evaluation/integration-english-real-20261014T031039Z/evidence.json) completed the original seven-turn assertions, verified the 15:30 receipt and replay, and produced one write dispatch. Earlier failed attempts are retained separately. A single successful rehearsal does not establish general English reliability.

The bounded cardiology demo supports English text input and English delivery: conversation responses, ordered time options, appointment history, confirmation labels and receipt display. Backend records and task facts remain canonical; localized presentation does not change the server-issued approval event, proposal binding, identity or idempotency key.

Refresh the local demo, select **English**, and start a new conversation. The language selector sends `audit.locale` outside the event. Direct API callers can send `en` or `zh-Hant`; an English initial cardiology request also establishes English delivery when the hint is absent. Subsequent approval responses retain that language. An explicit locale change affects presentation only.

Use `--demo-agent scripted --medical-data-profile live-demo-v2` for a rehearsal without model API calls. The following English path is verified:

| Turn | Input / action | Expected behavior |
| --- | --- | --- |
| 1 | Book a cardiology appointment next Tuesday afternoon | Discover cardiology, search afternoon times, draft 14:00. |
| 2 | Only after 3 PM | Replace the time constraint with strictly after 15:00, invalidate the earlier draft, draft 15:30. |
| 3 | Wait, do I have any other appointments? | Retrieve three synthetic appointment records without losing the booking task. |
| 4 | Will that clash with my existing appointments? | Explain that 15:30 does not overlap the active appointments in the lookup. |
| 5 | Go back to the appointment we were booking | Requery availability before resuming the draft. |
| 6 | The 3:30 PM one, please | Display an English formal confirmation; no write. |
| 7 | Click Approve booking | Execute once and report the verified receipt in English. |

Additional checks cover `Change it to exactly 3:30 PM` versus `Only after 3:30 PM` (15:30 versus 16:00), `The second one` (the published 15:00 option, blocked by the seeded overlap), and `OK, that should be fine` (no execution; an older card cannot be replayed). Explicit AM/PM clocks are converted to 24-hour afternoon constraints; morning and evening requests remain outside this demo's scope. This is not a general natural-language calendar parser.

English and Chinese use the same execution safeguards. Translating a label never translates an action event or a receipt/proposal identifier. The downloadable receipt uses the localized delivery copy; the saved backend receipt and task remain unchanged. Legacy examination, welfare and government workflows have not received full English conversation coverage in this change.

Browser recognition/TTS language and recorded-voice locale now follow the selector (`en-US` / `zh-HK`). Automated tests verify configuration and adapter routing. Microphone recognition accuracy, browser voices and real cloud STT/TTS were not tested; a locale setting is not evidence of their accuracy.

## Earlier English implementation verification — 2026-10-14

- 70 focused Python tests passed, including the four new English HTTP/MCP scenarios and Chinese medical regressions.
- 25 frontend tests passed, including locale metadata, unchanged action events, language-aware scenario previews and speech configuration.
- The unchanged eight scripted benchmark cases passed: TCR 8/8, SCR 47/47, UEC 0. [Regression evidence](../../outputs/evaluation/multi_turn/20261014T012038Z-65901342/report.md).
- [Complete English rehearsal](../../outputs/evaluation/english_demo/20261014T012905Z/report.md) and [observable delivery/backend evidence](../../outputs/evaluation/english_demo/20261014T012905Z/evidence.json) are saved separately. They use the production `ScriptedCardiologyClient`, real local HTTP/MCP, isolated `live-demo-v2` data and the fixed service clock 2026-10-13 09:00+08:00. The seven-turn flow and duplicate approval produce one new booking and one write dispatch. The earlier rehearsal remains in `20261014T012411Z`.
- Initial English tests exposed untranslated capacity and receipt labels. Those failed test logs remain in `.tmp/medical-profile-tests/`; the assertions and original benchmark were not weakened.
- At this earlier stage, no real-model English run had been performed. Those results establish the bounded scripted English path; the later integration rehearsal is linked above.

To rerun (allow local HTTP and subprocesses):

```powershell
$env:PYTHONUTF8='1'
python -X utf8 -m unittest middleware.tests.test_demo_english tests.test_english_medical_demo_e2e
node --test tests/frontend_cantonese_voice.test.mjs tests/frontend_demo_console.test.mjs tests/frontend_workspace_behavior.test.mjs tests/frontend_voice_cancel.test.mjs
python -m evals.multi_turn.runner --track scripted
```

The browser demo was restarted to load the new middleware while preserving its data directory. Any pending in-memory drafts must be started again; saved bookings remain. The separate acceptance runs do not consume the browser demo's available slots.
