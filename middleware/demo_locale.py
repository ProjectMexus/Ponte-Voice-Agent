"""Presentation-only English copy for the bounded medical demo."""
from copy import deepcopy
import re


def response_locale(audit, content="", previous=None):
    requested = audit.get("locale")
    if not isinstance(requested, str): requested = None
    if requested in {"en", "en-US", "en-GB"}: return "en"
    if requested in {"zh-Hant", "zh-HK", "zh-TW"}: return "zh-Hant"
    if previous in {"en", "zh-Hant"}: return previous
    return "en" if re.search(r"[a-zA-Z]", content) and not re.search(r"[\u3400-\u9fff]", content) else "zh-Hant"


_COPY = {
    "預約草稿（尚未掛號）": "Appointment draft (not booked)", "我的醫療預約": "My medical appointments",
    "選擇醫療服務": "Choose a medical service", "選擇預約時段": "Choose an appointment time",
    "確認預約": "Confirm appointment", "處理預約問題": "Review booking issue", "預約完成": "Appointment confirmed",
    "確認掛號": "Approve booking", "取消掛號": "Cancel booking", "修改時段": "Change time",
    "返回原預約": "Resume booking", "尚未掛號": "Not booked", "候選草稿": "Draft candidate",
    "預約資料查詢時間": "Appointments checked at", "撞期核對": "Time overlap check", "掛號狀態": "Booking status",
    "回執編號": "Receipt reference", "預約編號": "Appointment reference", "掛號編號": "Registration number",
    "收據編號": "Receipt reference", "發出時間": "Issued at",
    "最後更新": "Last updated", "處理原因": "Reason", "錯誤原因": "Reason", "目前階段": "Current stage",
    "有效期限": "Expires at", "確認編號": "Confirmation reference", "病人編號": "Patient reference",
    "未知服務": "Medical visit", "心臟超聲波檢查": "Cardiac ultrasound", "腹部超聲波檢查": "Abdominal ultrasound",
    "復康治療科": "Rehabilitation", "物理治療": "Physical therapy", "心臟科": "Cardiology", "影像科": "Imaging",
    "第一門診": "Main outpatient clinic", "影像中心": "Imaging centre", "復康治療室": "Rehabilitation room",
    "陳先生（模擬病人）": "Mr Chan (synthetic patient)", "陳醫生（模擬）": "Dr Chan (synthetic)",
    "李醫生（模擬）": "Dr Lee (synthetic)", "周醫生（模擬）": "Dr Chow (synthetic)",
    "陳先生": "Mr Chan", "陳醫生": "Dr Chan", "李醫生": "Dr Lee", "周醫生": "Dr Chow",
    "服務": "Service", "日期": "Date", "時間": "Time", "地點": "Location", "狀態": "Status",
    "病人": "Patient", "醫生": "Doctor", "參考編號": "Reference", "任務編號": "Task reference",
    "沒有資料": "No data", "已確認": "Confirmed", "已完成": "Completed", "沒有重疊": "No overlap",
    "已取消": "Cancelled", "時段": "Slot",
    "原因代碼": "Reason code", "原因": "Reason", "訊息": "Message", "說明": "Details",
    "請說明是查詢已有預約、返回掛號、修改時間，還是選定目前時段。": "Please clarify whether you want to check appointments, resume booking, change the time, or select a slot.",
}


def display_value(value):
    """Translate known mock display text on copies, never action event payloads."""
    if isinstance(value, str):
        for source in sorted(_COPY, key=len, reverse=True): value = value.replace(source, _COPY[source])
        value = re.sub(r"剩餘\s*(\d+)\s*名", r"\1 places remaining", value)
        return re.sub(r"第\s*(\d+)\s*個", r"Option \1", value).replace("：", ": ")
    if isinstance(value, list): return [display_value(item) for item in value]
    if isinstance(value, dict):
        return {key: deepcopy(item) if key in {"event", "options_presentation", "id", "digest", "hash"} or key.endswith("_id") else display_value(item) for key, item in value.items()}
    return deepcopy(value)


def english_response(result):
    facts, task, recovery = result.facts, result.task, result.recovery
    if recovery:
        messages = {
            "unsupported_demo_intent": "This demo supports cardiology next Tuesday afternoon. No booking was submitted. Please restate your request within that scope.",
            "outcome_needs_checking": "The booking outcome needs manual verification. New bookings for this patient are blocked. Do not retry or assume that restarting means no booking occurred.",
            "selection_unavailable": "That time is no longer available. Please select another time; no booking was submitted.",
            "proposal_expired": "The confirmation has expired. No booking was submitted. Please select a time again.",
            "modify_requested": "Please enter your new time preference. The previous proposal was not submitted.",
            "booking_rejected": "The service rejected the booking. There is no confirmed receipt. Please check the details and try again.",
            "step_limit": "This turn reached its step limit and paused. No booking was submitted.",
            "backend_unavailable": "The appointment lookup failed. No booking was submitted. Please try again later.",
            "agent_unavailable": "The model could not respond. The task is paused; no booking was submitted.",
        }
        message = recovery.get("message", "")
        text = messages.get(recovery.get("reason")) or (message if message and not re.search(r"[\u3400-\u9fff]", message) else "Please clarify the time or option you want. No booking was submitted.")
    elif result.receipt:
        text = f"Your appointment is confirmed. Receipt reference: {result.receipt.get('receipt_id', '')}."
        if facts.get("late_change_message"): text += " Your later request did not cancel or change the completed booking."
    elif task.get("status") == "cancelled": text = "This booking task was cancelled. No booking was submitted."
    elif result.confirmation:
        appointment = result.confirmation.get("appointment", {})
        text = f"No appointment has been booked yet. Review Cardiology on {appointment.get('date', '')} at {appointment.get('time', '')}, then click Approve booking to submit."
    elif facts.get("response_reason") == "needs_reselection" or not facts.get("selected_slot"):
        text = "The previous draft is no longer valid. Please select an available time. No booking was submitted."
    elif facts.get("phase") == "inquiry":
        records = (facts.get("appointments_snapshot") or {}).get("records")
        text = f"I found {len(records)} appointment records, including any cancellations. " if isinstance(records, list) else "I could not verify your existing appointments. "
        text += {"clear": "The selected time does not overlap the active appointments in this lookup.", "overlap": "The selected time overlaps an existing appointment. Please choose another time."}.get((facts.get("conflict_result") or {}).get("status"), "I cannot confirm whether the selected time overlaps another appointment.")
    else: text = "This is a draft; no appointment has been booked. Select a time to request a formal confirmation card."
    times = (facts.get("options_presentation") or {}).get("visible_times", [])
    if times and not recovery and not result.confirmation and not result.receipt and task.get("status") != "cancelled":
        text += " Available times: " + "; ".join(f"option {index}: {time}" for index, time in enumerate(times, 1)) + "."
    return {"display_text": text, "speech_text": text}
