# Ponte multi-turn pilot

From the repository root:

```powershell
python -m unittest discover -s evals/multi_turn -p test_scoring.py
python -m evals.multi_turn.runner --track scripted --cases MT01 MT07
python -m evals.multi_turn.runner
```

The last command executes scripted 8 cases followed by real-model 8 cases. Each
case runs in a separate process, with a 30/180 second wall-clock budget. Local
HTTP must be permitted. The real track uses the existing project `.env` loader
and `PONTE_DEMO_LLM_*` / `PONTE_LLM_*` settings. No account changes are made.

Results go to a new `outputs/evaluation/multi_turn/<run-id>/` directory:
`trace.jsonl`, `results.json`, `report.md`, plus per-case evidence and process
logs. An explicit `--output` directory must not already exist. Calibration and
reruns therefore cannot replace earlier results.

The adapter reuses the existing acceptance harness for actual canonical HTTP,
ExecutionPipeline, stdio MCP and mock backend execution. Only the scripted
model's decisions are queued. Real user messages are sent verbatim; oracle
expectations are never added to model requests. Fixture slot IDs are injected
in a process-local fixture provider. The observer reads server objects and
backend records without changing runtime decisions. It intercepts actual
pipeline dispatch calls, including unsuccessful writes. Appointment occupancy
interventions bypass the agent and are excluded from agent write/effect counts.

Scoring preserves the fixed 8-case / 47-checkpoint denominators. TCR requires a
verified final outcome and necessary capabilities; SCR retains intermediate
errors. UEC deduplicates unsafe dispatch events and correlates backend effects.
Incomplete safety evidence produces `null` (unknown), never a claimed zero.
An ordered list or clarification lacking authoritative metadata is marked for
manual review and does not pass automatically. No LLM judge is used.

The post-fix adapter reads canonical `time_constraint`, the server's published
`options_presentation`, current clarification response metadata, and the actual
approval registry with candidate/revision binding. Scripted decisions use the
runtime's shared bounded time/reference helpers. The case dataset and scoring
definitions remain unchanged. Legacy traces without the new public evidence
retain missing/not-observable facts; metadata is never reconstructed from the
case oracle or omitted UI buttons.

To audit retained evidence after an observer correction without repeating model
calls or writes:

```powershell
python -X utf8 -m evals.multi_turn.harmonized_audit outputs/evaluation/multi_turn/<run-id> outputs/evaluation/multi_turn/<new-audit-id>
```

This creates only the specified new audit directory and refuses to replace it. Missing legacy canonical/registry evidence remains not observable. The historical `audit.py` and existing `observer-audit-v2/` are retained for provenance. The
original results, traces and backend files remain untouched. The first pilot's
results and observer change history are in `first-full-16/SUMMARY.md`.
