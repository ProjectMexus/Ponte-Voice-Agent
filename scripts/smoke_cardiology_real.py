"""Opt-in real OpenAI smoke over HTTP → MCP → isolated mock backend.

Run manually; makes billable model calls and one mock booking. Keeps the fresh
dataset and evidence on failure as well as success; never touches existing data.
"""

from __future__ import annotations

from contextlib import ExitStack
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import sys
import threading
import uuid
from urllib.error import HTTPError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from middleware.config import load_dotenv
from middleware.demo_model import MODEL_TOOL_ALIASES
from middleware.intent import KeywordIntentRecognizer
from middleware.server import create_application, create_http_server
from mock_backends.core.persistence import JsonLinesTextRepository
from mock_backends.server import create_application as create_backend_application, make_request_handler
from scripts.demo_cardiology import rehearse


def serve(stack, server):
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def stop():
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)

    stack.callback(stop)


def smoke():
    load_dotenv()
    if not (os.environ.get("PONTE_DEMO_LLM_API_KEY") or os.environ.get("PONTE_LLM_API_KEY")):
        print("尚未驗證 real model：請在本機 .env 填入 API key。")
        return 2
    if os.environ.get("PONTE_DEMO_LLM_API_URL") != "https://api.openai.com/v1/chat/completions":
        print("請在本機設定 PONTE_DEMO_LLM_API_URL 為 OpenAI chat completions 網址。")
        return 2
    if os.environ.get("PONTE_DEMO_LLM_MODEL") != "gpt-4.1-mini":
        print("請在本機設定 PONTE_DEMO_LLM_MODEL=gpt-4.1-mini。")
        return 2

    data_dir = PROJECT_ROOT / f".demo-data-real-smoke-{uuid.uuid4().hex[:12]}"
    data_dir.mkdir(exist_ok=False)
    evidence = {"mode": "real", "model": "gpt-4.1-mini", "passed": False, "model_calls": []}
    print(f"Isolated data (retained): {data_dir}", flush=True)
    try:
        with ExitStack() as stack:
            backend = ThreadingHTTPServer(("127.0.0.1", 0), make_request_handler(create_backend_application(data_dir)))
            serve(stack, backend)
            app = create_application(
                f"http://127.0.0.1:{backend.server_port}", "PAT-REAL-SMOKE", "Bearer mock-user-token",
                demo_agent_mode="real", intent_recognizer=KeywordIntentRecognizer(),
            )
            stack.callback(app.close)
            provider = app.demo_workflow.client.client
            original_transport = provider._transport

            def record_transport(request, timeout):
                payload = json.loads(request.data)
                assert payload["model"] == "gpt-4.1-mini"
                names = [tool["function"]["name"] for tool in payload["tools"]]
                names.extend(call["function"]["name"] for message in payload["messages"] for call in message.get("tool_calls", []))
                assert all(re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", name) for name in names)
                try:
                    response = original_transport(request, timeout)
                except Exception as error:
                    cause = error
                    while cause.__cause__ is not None:
                        cause = cause.__cause__
                    if isinstance(cause, HTTPError):
                        evidence["provider_http_status"] = cause.code
                        try:
                            problem = json.loads(cause.read()).get("error", {})
                            # Record only structured identifiers, never provider
                            # prose, request headers, or credentials.
                            evidence["provider_error"] = {key: problem.get(key) for key in ("type", "code", "param")}
                        except (ValueError, AttributeError):
                            pass
                    raise
                calls = response["choices"][0]["message"].get("tool_calls", [])
                evidence["model_calls"].append([
                    {"id": call["id"], "name": call["function"]["name"], "arguments": json.loads(call["function"]["arguments"])} for call in calls
                ])
                if not calls:
                    evidence.setdefault("model_text_decisions", []).append(response["choices"][0]["message"].get("content"))
                return response

            provider._transport = record_transport
            middleware = create_http_server("127.0.0.1", 0, app)
            serve(stack, middleware)
            booked = rehearse(f"http://127.0.0.1:{middleware.server_port}")
            assert booked["task"]["facts"]["model_mode"] == "real"
            appointment = next(item for item in JsonLinesTextRepository(data_dir / "medical/appointments.txt").list()
                               if item.get("patient_id") == "PAT-REAL-SMOKE")
            assert len([item for item in JsonLinesTextRepository(data_dir / "medical/appointments.txt").list()
                        if item.get("patient_id") == "PAT-REAL-SMOKE"]) == 1
            selected = booked["task"]["facts"]["selected_slot"]
            assert appointment["status"] == "booked"
            assert appointment["department"]["id"] == "DEPT-CARDIO"
            assert appointment["slot_id"] == selected["id"] and appointment["start"] == selected["start"]
            assert appointment["start"][11:16] == "15:30"
            backend_task = JsonLinesTextRepository(data_dir / "medical/tasks.txt").get(appointment["task_id"])
            assert backend_task["status"] == "completed" and backend_task["appointment_id"] == appointment["id"]
            transcript = app.demo_workflow.transcript(booked["task"]["task_id"])
            pending = {}
            superseded = 0
            for message in transcript:
                for call in message.get("tool_calls", []):
                    assert call["function"]["name"] in MODEL_TOOL_ALIASES
                    assert call["id"] not in pending
                    pending[call["id"]] = call
                if message["role"] == "tool":
                    call = pending.pop(message["tool_call_id"])
                    if "SUPERSEDED" in message["content"]:
                        assert call["function"]["name"] == "medical.create_registration"
                        superseded += 1
            assert not pending and superseded == 1
            evidence.update(passed=True, appointment=appointment, backend_task=backend_task,
                            receipt=booked["receipt"], superseded_pairs=superseded)
            print("REAL MODEL PASS: backend booked 15:30; MED-REG receipt; one booking.", flush=True)
            return 0
    except Exception as error:
        # Do not print exception text/tracebacks that might contain credentials.
        evidence["failure_type"] = type(error).__name__
        print(f"尚未驗證 real model：smoke 未通過 ({type(error).__name__})；保留資料供查核。", flush=True)
        return 1
    finally:
        (data_dir / "real-smoke-evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(smoke())
