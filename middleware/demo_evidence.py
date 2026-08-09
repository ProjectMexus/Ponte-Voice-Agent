"""User-safe service evidence from executed operations and authoritative state.

This is a delivery audit, not model reasoning or an alternative approval path.
"""
from collections.abc import Mapping


_TOOL_OPERATIONS = {
    "medical.list_departments": ("查詢可用科室", "departments"),
    "medical.search_registration_slots": ("查詢可用時段", "slots"),
    "medical.get_my_appointments": ("查詢現有預約", "appointments"),
    "medical.create_registration": ("提交掛號要求", "booking"),
    "medical.list_appointment_services": ("查詢醫療服務", "services"),
    "medical.search_appointment_slots": ("查詢可用時段", "slots"),
    "medical.create_appointment": ("提交預約要求", "booking"),
    "one_account.get_cash_sharing_plan": ("查詢現金分享計劃", "cash"),
}


def record_tool_events(logs, *, at, offset=0):
    """Describe only observed allowlisted dispatches, without raw results or inferred milestones."""
    events = []
    for log in logs:
        if not isinstance(log, Mapping) or log.get("type") != "tool_execution":
            continue
        tool = log.get("tool")
        entry = _TOOL_OPERATIONS.get(tool) if isinstance(tool, str) else None
        if entry is None:
            continue
        title, operation = entry
        ok = log.get("ok") is True
        events.append({"id": f"E{offset + len(events) + 1}",
                       "kind": "booking_submitted" if operation == "booking" else "service_lookup",
                       "operation": operation, "title": title,
                       "detail": "已收到服務回覆。" if ok else "查詢或提交未能完成；以後續核對結果為準。",
                       "status": "completed" if ok else "failed", "at": at})
    return events


def constraint_text(value):
    if not isinstance(value, Mapping):
        return ""
    kind, time = value.get("kind"), value.get("time")
    if kind == "afternoon":
        return "下午"
    if kind == "exact" and isinstance(time, str):
        return f"指定 {time}"
    if kind == "lower_bound" and isinstance(time, str):
        return f"{time} 起（包含該時間）" if value.get("inclusive") is True else f"{time} 之後（不包含該時間）"
    return ""


def record_service_events(facts, logs, previous, *, phase, confirmation, receipt, recovery, at, offset):
    """Return only new, observed events; replaying an outcome adds no milestones."""
    current = {
        "revision": facts.get("intent_revision"), "candidate": facts.get("candidate_id"),
        "phase": phase, "confirmation": (confirmation or {}).get("confirmation_id"),
        "receipt": (receipt or {}).get("receipt_id"),
        "presentation": (facts.get("options_presentation") or {}).get("presentation_id"),
        "snapshot": (facts.get("appointments_snapshot") or {}).get("request_id"),
        "message": facts.get("response_message"),
    }
    events = []
    def add(kind, title, detail="", status="completed"):
        events.append({"id": f"E{offset + len(events) + 1}", "kind": kind, "title": title,
                       "detail": detail, "status": status, "at": at})
    if previous.get("revision") is not None and current["revision"] != previous["revision"]:
        add("constraints_updated", "已更新時間要求", constraint_text(facts.get("time_constraint")))
    if previous.get("candidate") and current["candidate"] != previous["candidate"] and not receipt:
        add("draft_invalidated", "先前的候選草稿已撤銷", f"{previous['candidate']} 不再可用；請以目前的時段與草稿為準。")
    if previous.get("confirmation") and current["confirmation"] != previous["confirmation"] and not receipt:
        add("approval_invalidated", "先前的確認已失效", "舊確認不能提交掛號；請以最新資料重新確認。")
    for log in logs:
        if not isinstance(log, Mapping):
            continue
        if log.get("type") == "tool_execution":
            events.extend(record_tool_events([log], at=at, offset=offset + len(events)))
        elif log.get("type") == "selection_resolved":
            reference = {"current": "目前候選草稿", "time": "指定的時間", "slot_id": "指定的時段編號", "ordinal": f"本次清單第 {log.get('ordinal', '')} 個時段"}.get(log.get("kind"), "你指定的時段")
            add("selection_resolved", "已理解所選時段", f"{reference}；會重新核對可用性，尚未提交。")
        elif log.get("type") == "confirmation_decision" and log.get("decision") == "approve":
            add("approval_received", "收到明確確認", "已驗證伺服器發出的確認操作，才提交掛號。")
    if current["presentation"] and current["presentation"] != previous.get("presentation"):
        count = len((facts.get("options_presentation") or {}).get("ordered_slot_ids", []))
        add("options_presented", "已更新可選時段", f"本次清單有 {count} 個時段；清單序號只對本次展示有效。")
    if current["candidate"] and current["candidate"] != previous.get("candidate"):
        start = (facts.get("selected_slot") or {}).get("start", "")
        add("draft_prepared", "已準備候選草稿", f"{start[:10]} {start[11:16]} · {current['candidate']}；尚未掛號。")
    if phase == "inquiry" and previous.get("phase") != "inquiry":
        add("booking_interrupted", "已暫停預約，查看現有紀錄", "原候選草稿仍保留，沒有提交掛號。" if current["candidate"] else "沒有提交掛號。")
    if previous.get("phase") == "inquiry" and phase != "inquiry" and current["candidate"] and any(e["title"] == "查詢可用時段" and e["status"] == "completed" for e in events):
        add("booking_resumed", "重新查詢後返回預約草稿", "已重新取得時段資料；草稿仍需選定及確認。")
    conflict = facts.get("conflict_result") or {}
    if current["snapshot"] and current["snapshot"] != previous.get("snapshot"):
        status = conflict.get("status")
        if status in {"clear", "overlap", "unknown"}:
            add("conflicts_checked", "已核對預約時間", {"clear": "目前取得的預約紀錄未見撞期。", "overlap": "發現預約時間重疊，不能確認這個草稿。", "unknown": "資料不足，未能排除撞期；不能確認掛號。"}[status], "completed" if status == "clear" else "attention")
    if confirmation and current["confirmation"] != previous.get("confirmation"):
        add("confirmation_ready", "最新草稿可供確認", "時段、病人及撞期資料已核對；只有按下確認才會提交。")
    if recovery and current["message"] != previous.get("message"):
        add("clarification" if facts.get("response_kind") == "clarification" else "needs_attention",
            "需要你澄清" if facts.get("response_kind") == "clarification" else "服務需要處理",
            str(recovery.get("message") or facts.get("response_message") or "請查看目前的服務提示。"), "attention")
    if receipt and current["receipt"] != previous.get("receipt"):
        add("receipt_verified", "掛號完成，回執已核對", f"{current['receipt']}；病人、科室、時段、開始時間及後端完成狀態一致。")
    return events, current
