"""Rehearse the approved story against an already running local HTTP stack."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from urllib.request import ProxyHandler, Request, build_opener


def rehearse(base_url: str) -> dict:
    opener = build_opener(ProxyHandler({}))
    with opener.open(f"{base_url}/api/health", timeout=15) as response:
        health = json.load(response)
    mode = health.get("demo_agent_mode", "off")
    if mode == "off":
        raise RuntimeError("Start the stack with --demo-agent scripted or real first")
    print(f"Model mode: {mode}; local HTTP → MCP → mock backend", flush=True)
    session = f"CARDIO-REHEARSAL-{uuid.uuid4().hex[:12]}"

    def send(event):
        request = Request(
            f"{base_url}/api/interactions",
            data=json.dumps({
                "routing": {"session_id": session, "interaction_id": f"INT-{uuid.uuid4().hex}"},
                "event": event,
            }, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"}, method="POST",
        )
        with opener.open(request, timeout=120) as response:
            return json.load(response)

    def approve(result):
        return next(action["event"] for action in result["workspace"]["actions"]
                    if action["event"].get("decision") == "approve")

    def draft(result, candidate_id, expected_time):
        assert result["receipt"] is None, result
        assert not any(a["event"].get("decision") == "approve" for a in result["workspace"]["actions"]), result
        assert result["task"]["facts"]["candidate_id"] == candidate_id, result
        assert result["task"]["facts"]["selected_slot"]["start"][11:16] == expected_time, result

    p1 = send({"type": "user_utterance", "content": "幫我預約下星期二的心臟科"})
    draft(p1, "P1", "14:00")
    print("Turn 1 / P1: 14:00 draft; no approval or booking", flush=True)
    p2 = send({"type": "user_utterance", "content": "下午三點後先得"})
    draft(p2, "P2", "15:30")
    task_id = p2["task"]["task_id"]
    revision = p2["task"]["facts"]["intent_revision"]
    print("Turn 2 / P2: 15:30 draft after constraint revision", flush=True)
    for number, text in ((3, "等等，我之前有冇其他預約？"),
                         (4, "咁會唔會撞時間？"),
                         (5, "好，返去頭先個預約")):
        result = send({"type": "user_utterance", "content": text})
        draft(result, "P2", "15:30")
        assert result["task"]["task_id"] == task_id, result
        assert result["task"]["facts"]["intent_revision"] == revision, result
        if number == 3:
            assert result["task"]["facts"]["phase"] == "inquiry", result
            snapshot = result["task"]["facts"]["appointments_snapshot"]
            assert snapshot and snapshot["source"] == "medical.get_my_appointments", result
            assert snapshot["records"] is not None, result
        elif number == 4:
            assert result["task"]["facts"]["phase"] == "inquiry", result
            assert result["task"]["facts"]["appointments_snapshot"] == snapshot, result
        elif number == 5:
            assert result["task"]["facts"]["phase"] == "awaiting_selection", result
        print(f"Turn {number}: {result['response']['display_text']}", flush=True)
    p2 = send({"type": "user_utterance", "content": "就15:30嗰個"})
    assert p2["task"]["status"] == "awaiting_confirmation", p2
    assert p2["receipt"] is None, p2
    assert p2["task"]["pending_confirmation"]["candidate_id"] == "P2", p2
    print("Turn 6 / A2: formal card issued; still not booked", flush=True)
    approved_action = approve(p2)
    booked = send(approved_action)
    assert booked["task"]["status"] == "completed", booked
    receipt = booked["receipt"]
    assert receipt["receipt_id"].startswith("MED-REG-"), booked
    repeated = send(approved_action)
    assert repeated["receipt"] == receipt, repeated
    print("Turn 7 / explicit approval: booked; repeated approval returns same receipt", flush=True)
    print(json.dumps(receipt, ensure_ascii=False, indent=2), flush=True)
    return booked


def main() -> None:
    # Keep Chinese receipt facts readable when a PowerShell demo saves output.
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--middleware-url", default="http://127.0.0.1:8090")
    args = parser.parse_args()
    rehearse(args.middleware_url.rstrip("/"))


if __name__ == "__main__":
    main()
