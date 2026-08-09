# Seven-turn cardiology demo on main

The restored `DemoMedicalWorkflow` shares main's frontend, `/api/interactions`, `SessionStore.transaction`, `ExecutionPipeline`, MCP subprocess and mock backend. It owns cardiology draft constraints, appointment snapshots and proposal validation. It does not replace `AgentOrchestrator` for other services.

## Run a rehearsal

From the repository root in PowerShell:

```powershell
$env:PONTE_AGENT_ENABLED = 'false'
$demoData = Join-Path (Get-Location) ('.demo-data-cardiology-' + [guid]::NewGuid().ToString('N'))
python scripts/run_stack.py --demo-agent scripted --medical-data-profile live-demo-v2 --data-dir $demoData
```

This turns off the separate general LLM agent for the rehearsal. The cardiology workflow uses scripted decisions, actual local HTTP/MCP calls, explicit approval, and isolated synthetic data. No provider API key is needed. The UI discloses **Scripted demo**.

Open the printed frontend URL. If the default ports are occupied, append `--backend-port 18189 --middleware-port 18199 --frontend-port 16179` and use the newly printed URL. Press `Ctrl-C` to stop the stack.

## Run the real model

Configure `PONTE_LLM_API_URL`, `PONTE_LLM_API_KEY` and `PONTE_LLM_MODEL` in the local `.env`. Use the full chat-completions URL. Optional `PONTE_DEMO_LLM_API_URL`, `PONTE_DEMO_LLM_API_KEY` and `PONTE_DEMO_LLM_MODEL` override those fields only for cardiology.

```powershell
$env:PONTE_AGENT_ENABLED = 'true'
$demoData = Join-Path (Get-Location) ('.demo-data-cardiology-real-' + [guid]::NewGuid().ToString('N'))
python scripts/run_stack.py --demo-agent real --medical-data-profile live-demo-v2 --data-dir $demoData
```

Both runtimes are available in this mode: new cardiology requests enter the bounded workflow; other services enter main's general agent. An active task retains its owner. A cardiology request cannot abandon a pending general-agent proposal. Completed cardiology tasks can yield to a new appointment enquiry or examination task; old approval events still require their original binding.

`PONTE_AGENT_ENABLED=true` alone enables the general agent, not the seven-turn workflow. `--demo-agent real` explicitly enables that workflow. Without CLI flags, `PONTE_DEMO_AGENT_MODE` accepts `off` (default), `scripted`, or `real`; `PONTE_MEDICAL_DATA_PROFILE` accepts `legacy` (default) or `live-demo-v2`.

## Conversation

Choose **EN** for English or **繁中** for Chinese. Use text for a rehearsal that does not depend on microphone or speech-provider availability.

| Turn | English | Cantonese | Expected behavior |
| --- | --- | --- | --- |
| 1 | Book a cardiology appointment next Tuesday afternoon. | 幫我預約下星期二的心臟科。 | Discover the department and slots; draft P1 at 14:00. |
| 2 | Only after 3 PM. | 下午三點後先得。 | Invalidate P1; draft P2 at 15:30. |
| 3 | Wait, do I have any other appointments? | 等等，我之前有冇其他預約？ | Query history without losing the booking. |
| 4 | Will that clash with my existing appointments? | 咁會唔會撞時間？ | Explain overlap using the appointment snapshot. |
| 5 | Go back to the appointment we were booking. | 好，返去頭先個預約。 | Resume and requery slot availability. |
| 6 | The 3:30 PM one, please. | 就 15:30 嗰個。 | Show the formal confirmation card; do not book. |
| 7 | Click **Approve booking**. | 點擊「確認掛號」。 | Validate approval, dispatch once and verify the receipt. |

The listed times assume a fresh `live-demo-v2` dataset. The service clock determines next Tuesday. Saved bookings consume slots; reusing data does not reset them. A stale or unavailable slot must cause reselection, not a fabricated success. See the [data profile](demo/Medical_Data_Profile.md).

## Execution boundaries

- Cardiology uses `medical.list_departments`, `medical.search_registration_slots`, `medical.get_my_appointments`, and approval-gated `medical.create_registration`.
- An exact server-issued action authorizes the write. Language changes and text such as “OK” do not authorize it.
- Explicit parsed time boundaries are checked against model decisions; contradictions receive one correction opportunity, then pause.
- Backend capacity checks and process-local write locking supplement idempotency. JSON records are not crash-atomic; no distributed exactly-once guarantee is claimed.
- Session history, proposals and uncertain-outcome blocks remain in memory. Restart does not prove a booking failed or recover pending approval.

## Verification

```powershell
python -m unittest tests.test_demo_agent_e2e tests.test_demo_round2_e2e tests.test_live_medical_demo_e2e tests.test_english_medical_demo_e2e tests.test_integrated_cardiology_routing -q
python -m unittest tests.test_agent_full_stack tests.test_english_interactions -q
python -m unittest discover -s evals/multi_turn -p 'test_*.py' -q
python -m evals.multi_turn.runner --track both
```

The last command makes billable provider calls for the real-model track. Each run creates a new directory. The original eight cases and historical records are retained; scripted, live-model, calibration and failed attempts remain separate. A passing single rehearsal is not a reliability estimate.

Supplementary diagrams of the bounded cardiology path: [Chinese SVG](architecture/Ponte_Demo_Architecture.svg) · [English SVG](architecture/Ponte_Demo_Architecture.en.svg). These describe that domain path, not the entire general-agent capability set. General runtime details remain in [AGENT_EXECUTION.md](AGENT_EXECUTION.md).
