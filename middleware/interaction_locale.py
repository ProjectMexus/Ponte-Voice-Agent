"""English presentation copies; authoritative events and facts are unchanged."""
from copy import deepcopy
import re

_COPY = {
    "我的醫療預約":"My medical appointments", "選擇醫療服務":"Choose a medical service",
    "選擇預約時段":"Choose an appointment time", "確認預約":"Confirm appointment",
    "預約完成":"Appointment confirmed", "處理預約問題":"Review booking issue",
    "現金分享計劃":"Cash sharing scheme", "處理現金分享查詢問題":"Review cash sharing issue",
    "腹部超聲波檢查":"Abdominal ultrasound", "心臟超聲波檢查":"Cardiac ultrasound", "物理治療":"Physical therapy",
    "第一門診":"Main outpatient clinic", "影像中心":"Imaging centre", "復康治療室":"Rehabilitation room",
    "服務":"Service", "日期":"Date", "時間":"Time", "地點":"Location", "狀態":"Status",
    "計劃名稱":"Plan name", "年度":"Year", "計劃狀態":"Plan status", "資格狀況":"Eligibility",
    "金額":"Amount", "貨幣":"Currency", "發放狀態":"Payment status", "預計發放日期":"Scheduled payment date",
    "最後更新":"Last updated", "符合本 Demo 測試用的基本資格資料。":"Meets the basic eligibility criteria for this demo.",
    "確認編號":"Confirmation reference", "收據編號":"Receipt reference", "發出時間":"Issued at",
    "原因":"Reason", "訊息":"Message", "說明":"Details", "原因代碼":"Reason code",
    "取消預約":"Cancel appointment", "修改資料":"Change details", "重新查詢":"Try again",
    "人工協助":"Ask for help", "取消查詢":"Cancel request", "分鐘":"minutes",
    "查詢可用科室":"Looked up departments", "查詢醫療服務":"Looked up medical services",
    "查詢可用時段":"Looked up appointment times", "查詢現有預約":"Looked up existing appointments",
    "查詢現金分享計劃":"Looked up cash sharing information", "提交預約要求":"Submitted the appointment request",
    "已收到服務回覆。":"Received the service response.", "服務未能完成，請查看目前的提示。":"The service could not complete. Review the current guidance.",
    "已整理待確認資料":"Prepared the details for your review", "資料已準備好，仍需由你確認才提交。":"The details are ready. Your confirmation is required before submission.",
    "已收到你的確認":"Received your confirmation", "已取消本次待提交操作":"Cancelled the pending operation",
    "等待修改資料":"Waiting for revised details", "已核對服務回執":"Verified the service receipt",
    "已完成回執核對，繼續整理服務結果。":"The receipt is verified. Preparing the service result.",
    "需要你的協助":"Your help is needed", "請查看本輪服務提示後再繼續。":"Review the current guidance before continuing.",
}

def display_text(value):
    if not isinstance(value, str):
        if isinstance(value, list): return [display_text(item) for item in value]
        if isinstance(value, dict): return {key: display_text(item) for key, item in value.items()}
        return deepcopy(value)
    for source in sorted(_COPY, key=len, reverse=True):
        value = value.replace(source, _COPY[source])
    return re.sub(r"剩餘\s*(\d+)\s*名", r"\1 places remaining", value)

def english_response(result):
    facts, task = result.facts, result.task
    intent, status = result.response_intent, task.get("status")
    if intent == "agent_response":
        text = str(facts.get("agent_message") or "Please continue.")
    elif intent == "cash_sharing_summary":
        plan = facts.get("plan", {})
        text = "I found your cash sharing information. This read-only lookup is complete."
        for label, value in (("Plan status", plan.get("status")), ("Eligibility", plan.get("eligibility", {}).get("status")), ("Payment status", plan.get("payout", {}).get("payment_status"))):
            if value is not None: text += f" {label}: {value}."
    elif intent == "appointment_list" or "appointments" in facts:
        text = f"I found {len(facts.get('appointments', []))} medical appointment records."
    elif status == "completed" or result.receipt:
        text = "Your appointment is confirmed."
        if result.receipt and result.receipt.get("receipt_id"): text += f" Receipt reference: {result.receipt['receipt_id']}."
    elif status == "cancelled": text = "This request was cancelled."
    elif result.recovery:
        message = result.recovery.get("message") or result.recovery.get("explanation") or ""
        text = message if message and not re.search(r"[\u3400-\u9fff]", message) else "The service needs your attention. Review the details and choose the next step."
    elif result.confirmation or status == "awaiting_confirmation":
        text = "Review the appointment details, then confirm to submit the booking."
    elif "slots" in facts or intent in {"select_slot", "slot_selection"}:
        text = f"I found {len(facts.get('slots', []))} available appointment times. Please choose a time."
    elif "services" in facts or intent in {"select_service", "service_selection"}:
        text = f"I found {len(facts.get('services', []))} medical services. Please choose a service."
    else: text = "Please choose the next step."
    return {"display_text": text, "speech_text": text, "locale": "en", "speech_locale": "en-US"}

def workspace_in_locale(workspace, locale):
    if locale != "en": return workspace
    result = deepcopy(workspace)
    result["title"] = display_text(result.get("title", ""))
    for field in result.get("fields", []):
        for key in ("label", "value"):
            if key in field: field[key] = display_text(field[key])
    for action in result.get("actions", []):
        if "label" in action: action["label"] = display_text(action["label"])
    for field in result.get("fields", []):
        action = field.get("action")
        if isinstance(action, dict) and "label" in action: action["label"] = display_text(action["label"])
    for event in result.get("activity", []):
        for key in ("title", "detail"):
            if key in event: event[key] = display_text(event[key])
    return result
