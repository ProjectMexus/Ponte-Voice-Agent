"""Rehearse the approved story against an already running local HTTP stack."""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from urllib.error import HTTPError
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

    p1 = send({"type": "user_utterance", "content": "心臟科下週二下午"})
    assert p1["task"]["status"] == "awaiting_confirmation", p1
    assert p1["task"]["facts"]["selected_slot"]["start"][11:16] == "14:00", p1
    old_action = approve(p1)
    print("P1: 14:00 proposed; paused without booking", flush=True)
    p2 = send({"type": "user_utterance", "content": "改為下午3點後"})
    assert p2["task"]["status"] == "awaiting_confirmation", p2
    assert p2["task"]["facts"]["selected_slot"]["start"][11:16] == "15:30", p2
    print("P2: 15:30 proposed after intent revision", flush=True)
    try:
        stale = send(old_action)
    except HTTPError as error:
        assert error.code == 400, error
        print("P1 stale approval: rejected", flush=True)
    else:
        assert stale.get("receipt") is None and stale["task"]["status"] != "completed", stale
        print("P1 stale approval: rejected without dispatch", flush=True)
    approved_action = approve(p2)
    booked = send(approved_action)
    assert booked["task"]["status"] == "completed", booked
    receipt = booked["receipt"]
    assert receipt["receipt_id"].startswith("MED-REG-"), booked
    repeated = send(approved_action)
    assert repeated["receipt"] == receipt, repeated
    print("P2 explicit confirmation: booked; repeated confirmation returns same receipt", flush=True)
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
