"""Isolated pilot runner. Run: python -m evals.multi_turn.runner

Each case is a child process with a wall-clock deadline. Results are append-only
within a freshly created directory; failed/partial checkpoints stay in scoring.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import traceback
import uuid

ROOT = Path(__file__).resolve().parents[2]
SPEC = Path(__file__).with_name("cases.json")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def append(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, ensure_ascii=False, default=str) + "\n")
        stream.flush()


def metadata(spec):
    from middleware.config import load_dotenv
    from middleware.demo_medical_workflow import DemoMedicalWorkflow
    from urllib.parse import urlsplit
    load_dotenv()
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    url = os.environ.get("PONTE_DEMO_LLM_API_URL") or os.environ.get("PONTE_LLM_API_URL", "")
    endpoint = urlsplit(url)
    sources = [ROOT / "middleware" / name for name in ("demo_medical_workflow.py", "demo_time.py", "demo_model.py", "interaction_delivery.py", "server.py", "execution.py")]
    return {"started_at_utc": datetime.now(timezone.utc).isoformat(), "app_revision": revision, "app_source_hashes": {str(p.relative_to(ROOT)): digest(p.read_bytes()) for p in sources},
            "harness_source_hashes": {p.name: digest(p.read_bytes()) for p in Path(__file__).parent.glob("*.py")},
            "dataset_hash": digest(SPEC.read_bytes()), "clock": spec["clock"], "timezone": spec["service_timezone"],
            "model": os.environ.get("PONTE_DEMO_LLM_MODEL") or os.environ.get("PONTE_LLM_MODEL", "gpt-4o-mini"),
            "endpoint_type": f"{endpoint.scheme}://{endpoint.hostname}" if endpoint.hostname else "unconfigured",
            "prompt_hash": digest((DemoMedicalWorkflow.SYSTEM_PROMPT + DemoMedicalWorkflow.ROUND2_PROMPT).encode()),
            "temperature": 0, "max_decisions": 4, "runner_version": 1}


def worker(args, spec):
    from evals.multi_turn.adapter import Adapter
    case = next(c for c in spec["cases"] if c["id"] == args.case)
    directory = Path(args.output)
    directory.mkdir(parents=True, exist_ok=True)
    evidence = {"case_id": case["id"], "track": args.track, "observations": [], "dispatches": [],
                "backend_effects": [], "coverage": {"dispatch_trace": False, "backend_effects": False}, "final": {}}
    adapter = None
    try:
        with Adapter(case, spec, args.track, directory) as adapter:
            for index, step in enumerate(case["steps"]):
                result = adapter.event(step)
                if "control" not in step:
                    evidence["observations"].append(result["observation"])
                evidence.update(adapter.snapshot())
                append(directory / "trace.jsonl", {"step": index + 1, "event": step, **result, "snapshot": adapter.snapshot()})
                save(directory / "evidence.json", evidence)
            failures = [exchange for exchange in evidence.get("model_exchanges", []) if exchange.get("error_type")]
            if failures:
                evidence["error"] = {"category": "infrastructure", "type": "model_provider_failure",
                                     "failures": [{k: row[k] for k in ("error_type", "root_error_type", "http_status") if k in row} for row in failures]}
    except Exception as error:
        # Exceptions can contain provider prose. Keep type and harness location,
        # never stringify a request or an arbitrary provider exception.
        missing_approval = isinstance(error, RuntimeError) and str(error).startswith("server issued no approval action")
        evidence["error"] = {"category": "approval" if missing_approval else "infrastructure" if args.track == "real_model" else "harness",
                             "type": "server_approval_unavailable" if missing_approval else type(error).__name__}
        append(directory / "trace.jsonl", {"error": evidence["error"], "frames": traceback.extract_tb(error.__traceback__).format()})
        if adapter is not None:
            try:
                evidence.update(adapter.snapshot())
            except Exception:
                pass
    provider_failures = [row for row in evidence.get("model_exchanges", []) if row.get("error_type")]
    if provider_failures:
        evidence["error"] = {"category": "infrastructure", "type": "model_provider_failure",
                             "failures": [{k: row[k] for k in ("error_type", "root_error_type", "http_status") if k in row} for row in provider_failures]}
    save(directory / "evidence.json", evidence)


def report(results, meta):
    lines = ["# Ponte multi-turn pilot", "", f"Dataset SHA256: `{meta['dataset_hash']}`", f"App revision: `{meta['app_revision']}`", "",
             "First attempts only. Calibration runs are retained separately. Missing checkpoints remain in the denominator.", "",
             "| Track | Cases | TCR | SCR | UEC | Coverage |", "|---|---:|---:|---:|---|---|"]
    for track in ("scripted", "real_model"):
        scores = [r for r in results if r["track"] == track]
        if not scores:
            continue
        complete = sum(bool(r.get("completed")) for r in scores)
        passed = sum(r.get("scr_passed", 0) for r in scores)
        uec = "unknown" if any(r.get("uec") is None for r in scores) else str(sum(r["uec"] for r in scores))
        covered = sum(r.get("coverage", {}).get("observed_checkpoints", 0) for r in scores)
        lines.append(f"| {track} | {len(scores)} | {complete}/8 | {passed}/47 | {uec} | {covered}/47 observed |")
    lines.extend(["", "| Track | Case | TCR | SCR | UEC | Reached checkpoints |", "|---|---|---|---:|---|---:|"])
    for row in results:
        lines.append(f"| {row['track']} | {row['case_id']} | {'pass' if row['completed'] else 'fail'} | {row['scr_passed']}/{row['scr_total']} | {row['uec'] if row['uec'] is not None else 'unknown'} | {row['coverage']['observed_checkpoints']}/{row['scr_total']} |")
    for result in results:
        lines.extend(["", f"## {result['track']} / {result['case_id']}", "", "```json", json.dumps(result, ensure_ascii=False, indent=2), "```"])
    lines.extend(["", "## Configuration", "", "```json", json.dumps(meta, ensure_ascii=False, indent=2), "```", ""])
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--track", choices=("scripted", "real_model", "both"), default="both")
    parser.add_argument("--cases", nargs="*", help="Subset for calibration; headline denominators stay fixed")
    parser.add_argument("--output")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--case", help=argparse.SUPPRESS)
    args = parser.parse_args()
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    if args.worker:
        worker(args, spec)
        return
    from evals.multi_turn.scoring import score_case
    meta = metadata(spec)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8]
    directory = Path(args.output) if args.output else ROOT / "outputs/evaluation/multi_turn" / run_id
    directory.mkdir(parents=True, exist_ok=False)
    save(directory / "metadata.json", meta)
    results = []
    tracks = ("scripted", "real_model") if args.track == "both" else (args.track,)
    for track in tracks:
        for case in spec["cases"]:
            if args.cases and case["id"] not in args.cases:
                continue
            target = directory / track / case["id"]
            target.mkdir(parents=True)
            command = [sys.executable, "-m", "evals.multi_turn.runner", "--worker", "--track", track, "--case", case["id"], "--output", str(target)]
            timed_out = False
            with (target / "process.log").open("w", encoding="utf-8") as log:
                process = subprocess.Popen(command, cwd=ROOT, stdout=log, stderr=log)
                try:
                    process.wait(timeout=30 if track == "scripted" else 180)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    if os.name == "nt":
                        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], stdout=log, stderr=log, check=False)
                    else:
                        process.kill()
                    process.wait()
            path = target / "evidence.json"
            evidence = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"observations": [], "coverage": {"dispatch_trace": False, "backend_effects": False}, "final": {}}
            if timed_out:
                evidence["error"] = {"category": "infrastructure", "type": "case_budget_exceeded"}
                evidence["coverage"] = {"dispatch_trace": False, "backend_effects": False}
            score = score_case(case, evidence.get("observations", []), dispatches=evidence.get("dispatches", []), backend_effects=evidence.get("backend_effects", []), coverage=evidence.get("coverage", {}), final=evidence.get("final", {}), error=evidence.get("error"))
            score.update({"track": track, "case_id": case["id"], "error": evidence.get("error")})
            results.append(score)
            save(target / "result.json", score)
            trace = target / "trace.jsonl"
            if trace.exists():
                with trace.open(encoding="utf-8") as stream:
                    for line in stream:
                        append(directory / "trace.jsonl", {"track": track, "case_id": case["id"], **json.loads(line)})
            save(directory / "results.json", {"metadata": meta, "results": results})
            (directory / "report.md").write_text(report(results, meta), encoding="utf-8")
            print(f"{track} {case['id']}: result saved", flush=True)
    print(directory, flush=True)


if __name__ == "__main__":
    main()
