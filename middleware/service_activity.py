"""Read-only, allowlisted presentation of recorded service operations.

This adapter does not choose tools, change tasks, or grant approval. Private
model messages, arguments, credentials, and raw service responses stay private.
"""
from collections.abc import Mapping


_TOOLS = {
    "medical.list_departments": ("查詢可用科室", "departments"),
    "medical.list_appointment_services": ("查詢醫療服務", "services"),
    "medical.search_registration_slots": ("查詢可用時段", "slots"),
    "medical.search_appointment_slots": ("查詢可用時段", "slots"),
    "medical.get_my_appointments": ("查詢現有預約", "appointments"),
    "medical.create_registration": ("提交掛號要求", "booking"),
    "medical.create_appointment": ("提交預約要求", "booking"),
    "one_account.get_cash_sharing_plan": ("查詢現金分享計劃", "cash"),
}


def _tool_event(tool, ok):
    entry = _TOOLS.get(tool) if isinstance(tool, str) else None
    if entry is None:
        return None
    title, operation = entry
    return {"kind": "booking_submitted" if operation == "booking" else "service_lookup",
            "operation": operation, "title": title,
            "detail": "已收到服務回覆。" if ok is True else "服務未能完成，請查看目前的提示。",
            "status": "completed" if ok is True else "failed"}


def project_agent_activity(trace):
    """Project stable event IDs from the main agent's existing execution trace."""
    events = []
    for entry in trace:
        if not isinstance(entry, Mapping) or type(entry.get("sequence")) is not int:
            continue
        kind = entry.get("event")
        event = None
        if kind == "execution_finished":
            event = _tool_event(entry.get("tool"), entry.get("ok"))
        elif kind == "approval_requested":
            event = {"kind": "confirmation_ready", "title": "已整理待確認資料",
                     "detail": "資料已準備好，仍需由你確認才提交。", "status": "completed"}
        elif kind == "approval_decision":
            decision = entry.get("decision")
            if decision in {"approve", "reject", "modify"}:
                title = {"approve": "已收到你的確認", "reject": "已取消本次待提交操作", "modify": "等待修改資料"}[decision]
                event = {"kind": "confirmation_decided", "title": title, "status": "completed"}
        elif kind == "agent_resumed":
            event = {"kind": "receipt_verified", "title": "已核對服務回執",
                     "detail": "已完成回執核對，繼續整理服務結果。", "status": "completed"}
        elif kind == "execution_paused":
            event = {"kind": "needs_attention", "title": "需要你的協助",
                     "detail": "請查看本輪服務提示後再繼續。", "status": "attention"}
        if event:
            events.append({"id": f"E{entry['sequence']}", **event})
    return events


def record_tool_events(logs, *, offset=0):
    events = []
    for entry in logs:
        if not isinstance(entry, Mapping) or entry.get("type") != "tool_execution":
            continue
        event = _tool_event(entry.get("tool"), entry.get("ok"))
        if event:
            events.append({"id": f"E{offset + len(events) + 1}", **event})
    return events


def public_activity(facts):
    events = facts.get("service_events")
    if not isinstance(events, list):
        return []
    public = []
    for event in events:
        if not isinstance(event, Mapping) or not isinstance(event.get("id"), str) or not isinstance(event.get("title"), str):
            continue
        value = {k: event[k] for k in ("id", "kind", "title", "detail", "status", "at") if isinstance(event.get(k), str)}
        if isinstance(event.get("operation"), str) and event["operation"] in {"departments", "services", "slots", "appointments", "cash", "booking"}:
            value["operation"] = event["operation"]
        public.append(value)
    return public
