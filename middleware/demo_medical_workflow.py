"""Small, process-local cardiology agent with explicitly approved writes.

InteractionCore owns the lock for the complete session turn.  This adapter owns
the authoritative transcript and proposals; browser task snapshots are views.
There is deliberately no restart recovery or durable approval authority here.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import json
import re
from threading import Lock
from typing import Any
import uuid

from MCP.registry import ToolRegistry

from .agent import AgentProtocolError, parse_agent_decision, project_registry_tools
from .contracts import PendingToolProposal, ToolCall, ToolExecutionResult
from .interaction_contracts import CanonicalInteractionResult, EventEnvelope, InteractionTask
from .llm_transport import ChatCompletionClient, ChatCompletionError, assistant_message, strict_json_content
from .medical_workflow import WorkflowResult


ALLOWLIST = frozenset({
    "medical.list_departments", "medical.search_registration_slots", "medical.create_registration", "medical.get_my_appointments",
})
CREATE = "medical.create_registration"
LOCAL_TZ = timezone(timedelta(hours=8))


def _identifier(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex.upper()}"


def _required(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value.strip()


def after_three(content: str) -> bool:
    """Recognize the one supported intent refinement independently of the model."""
    text = content.casefold().replace(" ", "")
    return bool(re.search(
        r"(?:after(?:15(?::00)?|3(?::00)?(?:pm)?)|(?:下午)?[3三](?:點|点|時|时|:00)?(?:之?[後后]|以[後后])|15(?::00)?(?:之?[後后]|以[後后]))",
        text,
    ))


def evaluate_conflicts(candidate, snapshot):
    """Compare aware half-open intervals; incomplete evidence fails closed."""
    result = {"status": "unknown", "candidate_id": candidate.get("id"), "snapshot_request_id": (snapshot or {}).get("request_id"), "conflicts": []}
    def interval(record):
        start, end = (datetime.fromisoformat(record[key].replace("Z", "+00:00")) for key in ("start", "end"))
        if start.utcoffset() is None or end.utcoffset() is None or end <= start:
            raise ValueError("invalid aware interval")
        return start, end
    try:
        start, end = interval(candidate)
        if not snapshot or not isinstance(snapshot.get("records"), list):
            return result
        unknown = False
        for record in snapshot["records"]:
            status = record.get("status")
            if status in {"cancelled", "canceled"}:
                continue
            if status not in {"booked", "confirmed"}:
                unknown = True
                continue
            try:
                other_start, other_end = interval(record)
                if start < other_end and other_start < end:
                    result["conflicts"].append({"id": record.get("id"), "start": record["start"], "end": record["end"]})
            except (KeyError, TypeError, ValueError, AttributeError):
                unknown = True
        result["status"] = "overlap" if result["conflicts"] else "unknown" if unknown else "clear"
    except (KeyError, TypeError, ValueError, AttributeError):
        pass
    return result


@dataclass(frozen=True)
class DemoProposal:
    frozen: PendingToolProposal
    session_id: str
    task_id: str
    revision: int
    call_id: str
    # Each action ID is issued once, and retains its original decision binding.
    actions: tuple[tuple[str, str], ...]


@dataclass
class _TaskState:
    session_id: str
    task: dict[str, Any]
    date: str
    transcript: list[dict[str, Any]]
    revision: int = 1
    after_three: bool = False
    departments: dict[str, dict[str, Any]] = field(default_factory=dict)
    slots: dict[str, dict[str, Any]] = field(default_factory=dict)
    proposals: dict[str, DemoProposal] = field(default_factory=dict)
    proposal_status: dict[str, str] = field(default_factory=dict)
    pending_id: str | None = None
    phase: str = "planning"
    candidate: DemoProposal | None = None
    candidate_number: int = 0
    verified_at: float = 0
    snapshot: dict[str, Any] | None = None
    resume_action: dict[str, Any] | None = None
    call_ids: set[str] = field(default_factory=set)


class DemoMedicalWorkflow:
    """Allowlisted model reads and immutable, button-approved registrations."""

    ROUND2_PROMPT = (
        'For each new user message with an existing candidate, first classify its meaning with strict JSON '
        '{"action":"query_appointments"}, {"action":"answer_question"}, {"action":"resume_booking"}, '
        '{"action":"select_slot"}, {"action":"update_constraints","after_three":true|false}, or '
        '{"action":"clarify","message":"..."}. No other fields are allowed. '
        'Queries and questions never change booking constraints. Resume is not selection or approval. '
        'create_registration only creates a draft; explicit slot selection creates a confirmation card. '
    )
    SYSTEM_PROMPT = (
        "You are Ponte's bounded cardiology demonstration agent. Use only provided tools, "
        "exactly one call per decision. First call medical.list_departments with exactly "
        '{"keyword":"Cardiology","active_only":true}. Keep the literal English keyword '
        '"Cardiology" even when the user writes Chinese; do not translate tool arguments. '
        "Then call medical.search_registration_slots for DEPT-CARDIO on the server's "
        "next_tuesday date with session=afternoon. "
        "Select the earliest returned available slot matching the user's latest intent. "
        "An afternoon request already provides enough information: choose 14:00 if available; "
        "do not ask whether the user prefers after 3 PM unless they request that change. "
        "When a matching slot exists, your next decision must call medical.create_registration "
        "with department_id, slot_id, consent=true and optionally the matching doctor_id. "
        "Do not ask for patient_id or additional confirmation in text before proposing. "
        "For 'after 3 PM' use timezone-aware slot times strictly after 15:00. "
        "There is no after_time search parameter. A create_registration call is only a "
        "draft proposal: the server waits for explicit slot selection before a confirmation button. Patient identity, trusted "
        "context and idempotency are injected by the server. Never infer approval from "
        "user text, speech, consent, or model output. Never claim a booking succeeded. "
        "If a proposal's tool result is SUPERSEDED, follow the new user intent. If a slot "
        "is unavailable, search again and propose a different returned slot. If no slot "
        "matches, return strict JSON {\"action\":\"clarify\",\"message\":\"...\"}. "
        "Any respond/clarify decision must have exactly action and message keys."
    )

    def __init__(
        self,
        pipeline: Any,
        patient_id: str,
        authorization: str,
        *,
        registry: ToolRegistry,
        client: ChatCompletionClient,
        clock: Any = None,
        mock_user_id: str = "USR-DEMO-001",
        max_decisions: int = 4,
    ) -> None:
        if isinstance(max_decisions, bool) or not isinstance(max_decisions, int) or not 1 <= max_decisions <= 4:
            raise ValueError("max_decisions must be between 1 and 4")
        self.pipeline = pipeline
        self.patient_id = _required(patient_id, "patient_id")
        self.authorization = _required(authorization, "authorization")
        self.mock_user_id = _required(mock_user_id, "mock_user_id")
        self.client = client
        self.clock = clock
        self.max_decisions = max_decisions
        self.model_mode = getattr(client, "mode", "real")
        self.tools = [tool for tool in project_registry_tools(registry) if tool["function"]["name"] in ALLOWLIST]
        if {tool["function"]["name"] for tool in self.tools} != ALLOWLIST:
            raise ValueError("demo registry must contain all three cardiology tools")
        # Identity is a server field even though the reusable backend input has it.
        create_parameters = next(tool for tool in self.tools if tool["function"]["name"] == CREATE)["function"]["parameters"]
        create_parameters["properties"].pop("patient_id", None)
        create_parameters["required"] = [name for name in create_parameters["required"] if name != "patient_id"]
        self._states: dict[str, _TaskState] = {}
        self._blocked_patients: set[str] = set()
        self._patient_guard = Lock()
        # This workflow has one configured patient. Serialize only its writes
        # across sessions so an unknown result blocks the next queued dispatch.
        self._patient_mutation_lock = Lock()

    def _now(self) -> datetime:
        if self.clock is None:
            value: Any = datetime.now(LOCAL_TZ)
        elif hasattr(self.clock, "now"):
            value = self.clock.now()
        elif callable(self.clock):
            value = self.clock()
        else:
            value = self.clock
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = datetime.fromtimestamp(value, LOCAL_TZ)
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("demo clock must return a timezone-aware datetime or UNIX timestamp")
        return value.astimezone(LOCAL_TZ)

    def transcript(self, task_id: str) -> list[dict[str, Any]]:
        """Return a diagnostic copy; callers cannot alter the next model request."""
        return deepcopy(self._states[task_id].transcript)

    def start(self, envelope: EventEnvelope, intent: Any = None) -> WorkflowResult:
        if envelope.event.get("type") != "user_utterance":
            raise ValueError("demo workflow starts with a user utterance")
        now = self._now()
        target_date = now.date() + timedelta(days=(1 - now.weekday()) % 7 or 7)
        task = InteractionTask(_identifier("TASK"), "medical_demo_agent", "awaiting_input", "agent_selection").to_dict()
        task["facts"] = {"engine": "demo_agent", "model_mode": self.model_mode, "intent_revision": 1, "requested_date": target_date.isoformat()}
        server_context = {"today": now.date().isoformat(), "next_tuesday": target_date.isoformat(), "timezone": "Asia/Macau"}
        state = _TaskState(envelope.session_id, task, target_date.isoformat(), [{
            "role": "system", "content": self.SYSTEM_PROMPT + self.ROUND2_PROMPT + "\nDEMO_SERVER_CONTEXT=" + json.dumps(server_context),
        }])
        self._states[task["task_id"]] = state
        content = _required(envelope.event.get("content"), "content")
        state.after_three = after_three(content)
        state.transcript.append({"role": "user", "content": content})
        logs = [{"type": "user_utterance", "content": content}]
        if self._patient_blocked():
            return self._uncertain(state, envelope, logs, "patient_blocked")
        if self._unsupported_intent(content, state.date):
            return self._pause(state, envelope, logs, "unsupported_demo_intent", "此示範只支援下週二下午的心臟科掛號，以及改為下午三點後；請重新輸入這個範圍的要求。")
        return self._run(state, envelope, logs)

    def handle(self, task_dict: dict[str, Any], envelope: EventEnvelope) -> WorkflowResult:
        state = self._states.get(task_dict.get("task_id"))
        if state is None or state.session_id != envelope.session_id:
            raise ValueError("demo task is not available in this session or process")
        event = envelope.event
        if event.get("task_id") is not None and event["task_id"] != state.task["task_id"]:
            raise ValueError("task_id does not match this demo task")
        logs: list[dict[str, Any]] = []
        if event.get("type") == "confirmation_decision":
            return self._confirmation(state, envelope, logs)
        if event.get("type") == "user_utterance":
            content = _required(event.get("content"), "content")
            if state.task["status"] == "completed":
                state.task["facts"]["late_change_message"] = "掛號已提交並完成；這則新要求沒有取消或更改已完成的掛號。"
                return self._outcome(state, envelope, "completed", logs)
            if self._patient_blocked():
                return self._uncertain(state, envelope, logs, "patient_blocked")
            if state.task["status"] == "cancelled":
                return self._outcome(state, envelope, "cancelled", logs)
            # Close any planning call before a new user turn; completed calls never
            # receive another result. Approval actions are independently revoked.
            self._invalidate_approval(state, "DEFERRED_FOR_QUERY")
            state.resume_action = None
            state.transcript.append({"role": "user", "content": content})
            if self._unsupported_intent(content, state.date) and self._changes_intent(content):
                state.candidate = None
                return self._pause(state, envelope, logs, "unsupported_demo_intent", "此示範只支援下週二心臟科下午或三點後；沒有提交掛號。")
            try:
                response = self.client.complete(self._model_messages(state, control=True), tools=deepcopy(self.tools), tool_choice="none", response_format={"type": "json_object"}, temperature=0, demo_control=True)
                control = dict(response) if "action" in response else dict(strict_json_content(response))
                state.transcript.append({"role": "assistant", "content": json.dumps(control, ensure_ascii=False)})
                action = control.get("action")
                allowed = {"action", "after_three"} if action == "update_constraints" else {"action", "message"} if action == "clarify" else {"action"}
                if set(control) != allowed:
                    raise ValueError("invalid control fields")
                if action == "query_appointments":
                    state.resume_action = {"type": "recovery_action", "action": "resume_booking", "action_id": _identifier("ACT"), "task_id": state.task["task_id"]}
                    state.phase = "inquiry"
                    self._query_appointments(state, logs)
                    return self._draft_outcome(state, envelope, logs)
                if action == "answer_question" and state.phase == "inquiry":
                    if not state.snapshot or self._now().timestamp() - state.snapshot["fetched_at"] > 60:
                        self._query_appointments(state, logs)
                    state.resume_action = {"type": "recovery_action", "action": "resume_booking", "action_id": _identifier("ACT"), "task_id": state.task["task_id"]}
                    return self._draft_outcome(state, envelope, logs)
                if action == "resume_booking" and state.candidate and state.phase == "inquiry":
                    self._resume_booking(state, logs)
                    return self._draft_outcome(state, envelope, logs)
                if action == "select_slot" and state.phase == "awaiting_selection" and state.candidate:
                    times = re.findall(r"\b\d{1,2}:\d{2}\b", content)
                    selected_time = datetime.fromisoformat(state.candidate.frozen.tool_arguments()["slot"]["start"]).astimezone(LOCAL_TZ).strftime("%H:%M")
                    if times and any(value != selected_time for value in times):
                        return self._pause(state, envelope, logs, "selection_mismatch", "請選定目前草稿的時段，或先修改時間要求；沒有提交掛號。")
                    if self._now().timestamp() - state.verified_at > 60:
                        original = state.candidate
                        self._resume_booking(state, logs)
                        if state.candidate is not original:
                            return self._draft_outcome(state, envelope, logs)
                    if not state.snapshot or self._now().timestamp() - state.snapshot["fetched_at"] > 60:
                        self._query_appointments(state, logs)
                    return self._issue_confirmation(state, envelope, logs)
                if action == "update_constraints" and type(control["after_three"]) is bool:
                    if self._unsupported_intent(content, state.date):
                        state.candidate = None
                        return self._pause(state, envelope, logs, "unsupported_demo_intent", "此示範只支援下週二心臟科下午或三點後；沒有提交掛號。")
                    if state.after_three != control["after_three"]:
                        state.revision += 1
                    state.after_three = control["after_three"]
                    state.task["facts"]["intent_revision"] = state.revision
                    state.candidate = None
                    state.slots.clear()
                    state.phase = "planning"
                    return self._run(state, envelope, logs)
                raise ValueError("decision is not legal in this phase")
            except Exception:
                return self._pause(state, envelope, logs, "agent_protocol_error", "未能安全理解此要求，沒有提交掛號。請重新說明。")
        if event.get("type") == "recovery_action":
            if self._patient_blocked():
                return self._uncertain(state, envelope, logs, "patient_blocked")
            if state.phase == "inquiry" and state.resume_action and dict(event) == state.resume_action:
                state.resume_action = None
                self._resume_booking(state, logs)
                return self._draft_outcome(state, envelope, logs)
            raise ValueError("invalid or stale resume action")
        if event.get("type") == "cancel_task":
            # Only confirmation actions are issued by this workflow.
            raise ValueError("use the server-issued proposal cancellation action")
        raise ValueError("unsupported demo workflow event")

    @staticmethod
    def _changes_intent(content: str) -> bool:
        text = content.casefold().strip().strip("。.!！?？")
        if text in {"yes", "ok", "okay", "confirm", "approve", "sure", "no", "是", "好", "好的", "確認", "确认", "係", "同意", "可以", "what happens next"}:
            return False
        return any(word in text for word in (
            "after", "before", "change", "instead", "later", "earlier", "afternoon", "morning",
            "改", "點", "点", "下午", "上午", "之後", "以后", "以後", "15:", "14:", "3 pm", "3pm",
        ))

    @staticmethod
    def _unsupported_intent(content: str, target_date: str) -> bool:
        """Fail closed on explicit constraints outside this single demo story.

        This is intentionally not a general date/time recognizer. In particular,
        a changed date or morning request must not keep the old afternoon slot.
        """
        text = content.casefold().replace(" ", "")
        if any(word in text for word in (
            "morning", "evening", "tonight", "tomorrow", "today", "before", "earlier",
            "nextmonth", "nextyear", "下個月", "下个月", "明年",
            "上午", "早上", "晚上", "今晚", "明天", "聽日", "今天", "今日", "之前", "以前", "三點前", "3點前",
            "骨科", "婦科", "妇科", "皮膚科", "皮肤科", "影像科", "超聲", "超声", "復康", "复康",
            "monday", "wednesday", "thursday", "friday", "saturday", "sunday",
            "星期一", "星期三", "星期四", "星期五", "星期六", "星期日", "星期天",
            "週一", "週三", "週四", "週五", "週六", "週日", "周一", "周三", "周四", "周五", "周六", "周日",
        )):
            return True
        if any(value != target_date for value in re.findall(r"\d{4}-\d{2}-\d{2}", text)):
            return True
        # Only the after-three threshold is supported; do not silently weaken
        # another explicit after/before time into the original afternoon request.
        if ("after" in text or any(word in text for word in ("點後", "点后", "點之後", "点之后", "時後", "时后"))) and not after_three(content):
            return True
        if any(word in text for word in ("after4", "after16", "四點", "四点", "4點", "4点", "16:00", "兩點後", "两点后", "2點後", "2点后")):
            return True
        if any(word in text for word in ("改", "change", "instead")) and not (after_three(content) or any(word in text for word in ("下午", "afternoon", "下週二", "下周二", "nexttuesday", "14:00", "2pm", "兩點", "两点"))):
            return True
        return False

    def _model_messages(self, state, *, control):
        messages = deepcopy(state.transcript)
        context = {"phase": state.phase, "candidate_id": state.task["facts"].get("candidate_id"), "candidate": state.candidate.frozen.tool_arguments() if state.candidate else None, "current_verified_slots": list(state.slots.values()), "after_three": state.after_three, "intent_revision": state.revision, "conflict_result": state.task["facts"].get("conflict_result")}
        instruction = "Classify only the latest user message using the Round2 control JSON schema. Do not call tools." if control else "Planning mode: do not classify again. Call the next catalogue/search/create draft tool using current server constraints. If current_verified_slots is empty, previous search results are invalid for this revision: search again before create. Only propose slots in current_verified_slots."
        messages.append({"role": "system", "content": instruction + " SERVER_STATE=" + json.dumps(context, ensure_ascii=False)})
        return messages

    def _run(self, state: _TaskState, envelope: EventEnvelope, logs: list[dict[str, Any]]) -> WorkflowResult:
        for _ in range(self.max_decisions):
            try:
                response = self.client.complete(self._model_messages(state, control=False), tools=deepcopy(self.tools), tool_choice="auto", response_format={"type": "json_object"}, temperature=0)
                decision = parse_agent_decision(response)
                if decision.action != "tool_call":
                    # Model prose never establishes completion or authority.
                    return self._pause(state, envelope, logs, "agent_paused", "模型已暫停。請提供有效的心臟科時段要求，再由確認按鈕提交。")
                name = decision.tool_name
                if name not in ALLOWLIST or not isinstance(decision.arguments, Mapping):
                    raise AgentProtocolError("tool is outside the demo allowlist")
                arguments = dict(decision.arguments)
                self._validate_arguments(state, name, arguments)
                if name == "medical.get_my_appointments":
                    raise AgentProtocolError("query requires semantic inquiry decision")
                message, call_id = self._assistant_call(response, name, arguments)
                if call_id in state.call_ids:
                    raise AgentProtocolError("assistant reused an earlier call ID")
                state.call_ids.add(call_id)
                state.transcript.append(message)
                if name == CREATE:
                    return self._propose(state, envelope, logs, call_id, arguments)
                result = self._dispatch(name, arguments, call_id, logs)
                self._tool_result(state, call_id, result.to_dict())
                if not result.ok:
                    return self._pause(state, envelope, logs, "backend_unavailable", "查詢暫時未能完成；沒有提交掛號。請稍後重新提出要求。")
                self._cache_read(state, name, result)
            except (AgentProtocolError, ChatCompletionError, TypeError, ValueError, KeyError):
                return self._pause(state, envelope, logs, "agent_protocol_error", "模型回覆或服務資料不符合此示範的工具規則，已安全暫停。")
            except Exception:
                return self._pause(state, envelope, logs, "agent_unavailable", "模型暫時未能回應，已暫停；沒有提交掛號。")
        return self._pause(state, envelope, logs, "step_limit", "已達此回合的服務步數上限，已暫停；沒有提交掛號。")

    @staticmethod
    def _assistant_call(response: Mapping[str, Any], name: str, arguments: Mapping[str, Any]) -> tuple[dict[str, Any], str]:
        if "action" not in response:
            message = assistant_message(response)
            native = message.get("tool_calls")
            if native is not None:
                # parse_agent_decision has already enforced exactly one call.
                call = native[0]
                call_id = _required(call.get("id"), "assistant tool call ID")
                if call.get("type") != "function" or message.get("content") is not None and not isinstance(message.get("content"), str):
                    raise AgentProtocolError("invalid assistant tool message")
                return {"role": "assistant", "content": message.get("content"), "tool_calls": [deepcopy(dict(call))]}, call_id
        call_id = _identifier("CALL")
        return {"role": "assistant", "content": None, "tool_calls": [{
            "id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(dict(arguments), ensure_ascii=False)},
        }]}, call_id

    def _validate_arguments(self, state: _TaskState, name: str, arguments: dict[str, Any]) -> None:
        if name == "medical.list_departments":
            if set(arguments) != {"keyword", "active_only"} or arguments.get("keyword") != "Cardiology" or arguments.get("active_only") is not True:
                raise AgentProtocolError("demo department lookup must target active Cardiology")
        elif name == "medical.search_registration_slots":
            if not {"department_id", "date", "session"}.issubset(arguments) or set(arguments) - {"department_id", "date", "session", "doctor_id", "location_id"}:
                raise AgentProtocolError("unsupported slot search arguments")
            if not state.departments.get("DEPT-CARDIO") or arguments["department_id"] != "DEPT-CARDIO" or arguments["date"] != state.date or arguments["session"] != "afternoon":
                raise AgentProtocolError("slot search does not match the server demo context")
        elif name == "medical.get_my_appointments":
            if arguments:
                raise AgentProtocolError("appointments query input must be empty")
        else:
            if not {"department_id", "slot_id", "consent"}.issubset(arguments) or set(arguments) - {"patient_id", "department_id", "slot_id", "doctor_id", "consent"}:
                raise AgentProtocolError("unsupported registration proposal arguments")
            if arguments.get("patient_id", self.patient_id) != self.patient_id or arguments["department_id"] != "DEPT-CARDIO" or arguments["consent"] is not True:
                raise AgentProtocolError("registration input disagrees with server identity or consent")
            slot = state.slots.get(arguments["slot_id"])
            if not slot or not self._eligible_slot(state, slot):
                raise AgentProtocolError("registration slot was not returned for the current intent")
            if "doctor_id" in arguments and arguments["doctor_id"] != slot.get("doctor_id"):
                raise AgentProtocolError("doctor does not match the server slot")

    def _cache_read(self, state: _TaskState, name: str, result: ToolExecutionResult) -> None:
        payload = result.data
        if not isinstance(payload, Mapping) or not isinstance(payload.get("data"), list) or not all(isinstance(item, Mapping) for item in payload["data"]):
            raise ValueError("invalid medical catalogue response")
        records = deepcopy(payload["data"])
        if name == "medical.list_departments":
            state.departments = {item["id"]: item for item in records if item.get("id") == "DEPT-CARDIO" and item.get("active") is True}
            if not state.departments:
                raise ValueError("active cardiology department missing")
            department = state.departments["DEPT-CARDIO"]
            state.task["facts"]["department"] = deepcopy(department)
            state.task["facts"]["service"] = {"id": department["id"], "name": department.get("name", "心臟科")}
        else:
            state.slots = {item["id"]: item for item in records if isinstance(item.get("id"), str) and self._eligible_slot(state, item)}
            state.task["facts"]["slots"] = deepcopy(list(state.slots.values()))

    def _eligible_slot(self, state: _TaskState, slot: Mapping[str, Any]) -> bool:
        try:
            start = datetime.fromisoformat(slot["start"])
            if start.tzinfo is None or start.utcoffset() is None:
                return False
            local = start.astimezone(LOCAL_TZ)
            minute = local.hour * 60 + local.minute
            return (
                slot.get("department_id") == "DEPT-CARDIO" and local.date().isoformat() == state.date
                and start > self._now() and 12 * 60 <= minute < 18 * 60
                and (not state.after_three or minute > 15 * 60)
                and isinstance(slot.get("remaining"), (int, float)) and not isinstance(slot.get("remaining"), bool)
                and slot["remaining"] > 0 and slot.get("status") == "free"
            )
        except (KeyError, TypeError, ValueError):
            return False

    def _propose(self, state: _TaskState, envelope: EventEnvelope, logs: list[dict[str, Any]], call_id: str, arguments: dict[str, Any], *, planning_call: bool = True) -> WorkflowResult:
        slot = deepcopy(state.slots[arguments["slot_id"]])
        final_input = {"patient_id": self.patient_id, "department_id": "DEPT-CARDIO", "slot_id": slot["id"], "consent": True}
        if slot.get("doctor_id"):
            final_input["doctor_id"] = slot["doctor_id"]
        frozen = PendingToolProposal.create(CREATE, {
            "input": final_input, "slot": slot, "session_id": state.session_id,
            "task_id": state.task["task_id"], "intent_revision": state.revision, "candidate_id": f"P{state.candidate_number + 1}",
        }, "R2", now=self._now().timestamp())
        state.candidate_number += 1
        state.candidate = DemoProposal(frozen, state.session_id, state.task["task_id"], state.revision, call_id, ())
        state.verified_at = self._now().timestamp()
        state.phase = "awaiting_selection"
        if planning_call:
            self._tool_result(state, call_id, {"ok": False, "executed": False, "error": {"code": "DRAFT_ONLY"}})
        state.task["facts"].update({"candidate_id": f"P{state.candidate_number}", "selected_slot": slot, "slot_id": slot["id"]})
        return self._draft_outcome(state, envelope, logs)

    def _invalidate_approval(self, state, reason):
        if state.pending_id:
            state.proposal_status[state.pending_id] = reason.lower()
            state.pending_id = None
        state.task["pending_confirmation"] = None

    def _read_exchange(self, state, name, arguments, logs):
        call_id = _identifier("READ")
        state.transcript.append({"role": "assistant", "content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}]})
        result = self._dispatch(name, arguments, call_id, logs)
        self._tool_result(state, call_id, result.to_dict())
        return result

    def _query_appointments(self, state, logs):
        result = self._read_exchange(state, "medical.get_my_appointments", {}, logs)
        payload = result.data if isinstance(result.data, Mapping) else {}
        records = payload.get("data")
        meta = payload.get("meta", {})
        valid = result.ok and isinstance(records, list) and all(isinstance(r, Mapping) for r in records) and meta.get("page", 1) == 1 and not meta.get("has_next", False) and meta.get("total", len(records)) <= len(records)
        state.snapshot = {"records": deepcopy(records) if valid else None, "fetched_at": self._now().timestamp(), "patient_id": self.patient_id, "request_id": result.request_id, "task_id": state.task["task_id"], "revision": state.revision, "source": "medical.get_my_appointments"}

    def _resume_booking(self, state, logs):
        state.phase = "resume_check"
        result = self._read_exchange(state, "medical.search_registration_slots", {"department_id": "DEPT-CARDIO", "date": state.date, "session": "afternoon"}, logs)
        if not result.ok:
            state.verified_at = 0
            return
        self._cache_read(state, "medical.search_registration_slots", result)
        old = state.candidate
        slot = old.frozen.tool_arguments()["slot"]
        current = state.slots.get(slot["id"])
        if old.frozen.is_expired(self._now().timestamp()) or current != slot:
            state.candidate = None
            state.task["facts"].pop("selected_slot", None)
            state.task["facts"].pop("slot_id", None)
            state.task["facts"].pop("candidate_id", None)
            if current:
                self._propose(state, EventEnvelope("REVALIDATE", state.session_id, {"type": "user_utterance", "content": "revalidation"}), logs, _identifier("DRAFT"), {"slot_id": current["id"]}, planning_call=False)
            state.task["facts"]["invalidation_message"] = "原草稿已失效；請重新選擇，沒有提交掛號。"
        else:
            state.verified_at = self._now().timestamp()
        if not state.snapshot or self._now().timestamp() - state.snapshot["fetched_at"] > 60:
            self._query_appointments(state, logs)
        state.phase = "awaiting_selection"

    def _draft_outcome(self, state, envelope, logs):
        facts = state.task["facts"]
        facts["phase"] = state.phase
        facts["appointments_snapshot"] = deepcopy(state.snapshot)
        conflict = evaluate_conflicts(state.candidate.frozen.tool_arguments()["slot"] if state.candidate else {}, state.snapshot)
        facts["conflict_result"] = conflict
        facts["round2_message"] = ("目前未能核實預約，不能確認沒有撞期。" if conflict["status"] == "unknown" else "這個時段與現有預約時間重疊，請選其他時段。" if conflict["status"] == "overlap" else "目前查詢的時間區間沒有重疊。") if state.phase == "inquiry" else "這是候選草稿，尚未掛號；請選定時段才建立正式確認卡。"
        state.task.update({"status": "awaiting_input", "current_step": "select_slot", "recovery": None, "pending_confirmation": None})
        return self._outcome(state, envelope, "slot_selection", logs)

    def _issue_confirmation(self, state, envelope, logs):
        candidate = state.candidate
        if not candidate or state.phase != "awaiting_selection":
            return self._draft_outcome(state, envelope, logs)
        conflict = evaluate_conflicts(candidate.frozen.tool_arguments()["slot"], state.snapshot)
        if candidate.frozen.is_expired(self._now().timestamp()) or self._now().timestamp() - state.verified_at > 60 or conflict["status"] != "clear":
            return self._draft_outcome(state, envelope, logs)
        frozen = PendingToolProposal.create(CREATE, candidate.frozen.tool_arguments(), "R2", now=candidate.frozen.created_at)
        call_id = _identifier("EXEC")
        proposal = DemoProposal(frozen, state.session_id, state.task["task_id"], state.revision, call_id, tuple((decision, _identifier("ACT")) for decision in ("approve", "reject", "modify")))
        state.proposals[frozen.proposal_id] = proposal
        state.proposal_status[frozen.proposal_id] = "pending"
        state.pending_id = frozen.proposal_id
        state.phase = "awaiting_approval"
        state.task["facts"]["phase"] = state.phase
        state.task["facts"]["round2_message"] = "尚未掛號；請核對病人、時段與撞期資料，點擊批准才提交。"
        state.task.update({"status": "awaiting_confirmation", "current_step": "confirm_registration", "recovery": None})
        state.task["pending_confirmation"] = {"confirmation_id": frozen.proposal_id, "candidate_id": state.task["facts"]["candidate_id"], "intent_revision": state.revision, "digest": frozen.proposal_hash, "expires_at": frozen.expires_at, "appointment": self._slot_details(state, frozen.tool_arguments()["slot"]), "patient_id": self.patient_id, "conflict_result": conflict, "fetched_at": state.snapshot["fetched_at"]}
        return self._outcome(state, envelope, "request_confirmation", logs)

    def _confirmation(self, state: _TaskState, envelope: EventEnvelope, logs: list[dict[str, Any]]) -> WorkflowResult:
        event = envelope.event
        proposal = state.proposals.get(event.get("confirmation_id"))
        if proposal is None:
            raise ValueError("confirmation is not a server-issued demo proposal")
        issued_id = dict(proposal.actions).get(event.get("decision"))
        expected = {"type": "confirmation_decision", "task_id": proposal.task_id, "confirmation_id": proposal.frozen.proposal_id, "candidate_id": state.task["facts"]["candidate_id"], "decision": event.get("decision"), "action_id": issued_id}
        if not issued_id or dict(event) != expected or envelope.session_id != proposal.session_id:
            raise ValueError("confirmation action is not the exact server-issued action")
        status = state.proposal_status[proposal.frozen.proposal_id]
        if status == "executed" and event["decision"] == "approve":
            return self._outcome(state, envelope, "completed", logs)
        if status != "pending" or state.pending_id != proposal.frozen.proposal_id or proposal.revision != state.revision:
            raise ValueError("confirmation is stale or has already been consumed")
        if state.phase != "awaiting_approval" or not state.candidate or proposal.frozen.tool_arguments() != state.candidate.frozen.tool_arguments():
            raise ValueError("approval phase mismatch")
        if event["decision"] == "approve" and (self._now().timestamp() - state.verified_at > 60 or not state.snapshot or self._now().timestamp() - state.snapshot["fetched_at"] > 60):
            self._invalidate_approval(state, "STALE")
            original = state.candidate
            self._resume_booking(state, logs)
            if state.candidate is not original:
                return self._draft_outcome(state, envelope, logs)
            return self._issue_confirmation(state, envelope, logs) if state.candidate else self._draft_outcome(state, envelope, logs)
        if not proposal.frozen.verify_integrity():
            raise ValueError("proposal integrity failed")
        if proposal.frozen.is_expired(self._now().timestamp()):
            self._close_pending(state, "EXPIRED", "Proposal expired without execution.")
            return self._pause(state, envelope, logs, "proposal_expired", "確認已過期，沒有提交掛號。請重新提出時段要求。")
        if event["decision"] != "approve":
            self._close_pending(state, "REJECTED" if event["decision"] == "reject" else "SUPERSEDED", "User rejected or requested modification; no write was submitted.")
            if event["decision"] == "reject":
                state.task.update({"status": "cancelled", "current_step": "cancelled", "recovery": None})
                return self._outcome(state, envelope, "cancelled", logs)
            return self._pause(state, envelope, logs, "modify_requested", "請輸入新的時段要求；原提案沒有提交。")
        with self._patient_mutation_lock:
            outcome = self._submit_approved(state, envelope, logs, proposal)
        if outcome is not None:
            return outcome
        # A definitive slot-loss result can search for a replacement. Do not
        # hold the patient's mutation lock while querying or waiting on a model.
        return self._run(state, envelope, logs)

    def _submit_approved(self, state: _TaskState, envelope: EventEnvelope, logs: list[dict[str, Any]], proposal: DemoProposal) -> WorkflowResult | None:
        """Check, dispatch and classify while holding the patient mutation lock."""
        if self._patient_blocked():
            return self._uncertain(state, envelope, logs, "patient_blocked")
        # A different session's write may have held the lock until expiry.
        if proposal.frozen.is_expired(self._now().timestamp()):
            self._close_pending(state, "EXPIRED", "Proposal expired while waiting for the patient write lock.")
            return self._pause(state, envelope, logs, "proposal_expired", "確認已過期，沒有提交掛號。請重新提出時段要求。")
        frozen_data = proposal.frozen.tool_arguments()
        slot = frozen_data["slot"]
        if not self._eligible_slot(state, slot):
            self._close_pending(state, "EXPIRED", "Proposed slot is no longer valid for this intent.")
            return self._pause(state, envelope, logs, "proposal_expired", "時段已失效，沒有提交掛號。請重新查詢。")
        state.proposal_status[proposal.frozen.proposal_id] = "submitting"
        state.task.update({"status": "executing", "current_step": "create_registration"})
        logs.append({"type": "confirmation_decision", "decision": "approve", "proposal_id": proposal.frozen.proposal_id})
        state.transcript.append({"role": "assistant", "content": None, "tool_calls": [{"id": proposal.call_id, "type": "function", "function": {"name": CREATE, "arguments": json.dumps(frozen_data["input"])}}]})
        result = self._dispatch(CREATE, frozen_data["input"], proposal.call_id, logs, idempotency_key=f"IDEMP-DEMO-{state.candidate.frozen.proposal_id}")
        self._tool_result(state, proposal.call_id, result.to_dict())
        state.pending_id = None
        state.task["pending_confirmation"] = None
        if not result.ok:
            state.proposal_status[proposal.frozen.proposal_id] = "failed"
            error = dict(result.error or {})
            code = str(error.get("code", "UNKNOWN"))
            if code in {"SLOT_NOT_AVAILABLE", "SLOT_NOT_FOUND"}:
                state.slots.clear()
                logs.append({"type": "slot_unavailable", "proposal_id": proposal.frozen.proposal_id})
                return None
            if self._ambiguous(error):
                return self._uncertain(state, envelope, logs, code)
            return self._pause(state, envelope, logs, "booking_rejected", "服務拒絕了掛號，沒有成功收據。請檢查資料後重新提出要求。")
        try:
            appointment, receipt = self._verify_receipt(state, proposal, result)
        except (ValueError, TypeError, KeyError):
            state.proposal_status[proposal.frozen.proposal_id] = "unverified"
            return self._uncertain(state, envelope, logs, "invalid_backend_response")
        state.proposal_status[proposal.frozen.proposal_id] = "executed"
        state.phase = "completed"
        state.task["facts"].pop("round2_message", None)
        state.task["facts"]["appointment"] = appointment
        state.task.update({"status": "completed", "current_step": "complete", "receipt": receipt, "recovery": None})
        logs.append({"type": "execution_completed", "receipt_id": receipt["receipt_id"], "proposal_id": proposal.frozen.proposal_id})
        return self._outcome(state, envelope, "completed", logs)

    def _close_pending(self, state: _TaskState, code: str, message: str) -> None:
        if state.pending_id is None:
            return
        proposal = state.proposals[state.pending_id]
        # Approval has no open model call; only actual execution adds a call/result.
        state.proposal_status[state.pending_id] = code.casefold()
        state.pending_id = None
        state.task["pending_confirmation"] = None

    @staticmethod
    def _tool_result(state: _TaskState, call_id: str, result: Mapping[str, Any]) -> None:
        state.transcript.append({"role": "tool", "tool_call_id": call_id, "content": json.dumps(dict(result), ensure_ascii=False)})

    def _dispatch(self, name: str, input_data: Mapping[str, Any], call_id: str, logs: list[dict[str, Any]], *, idempotency_key: str | None = None) -> ToolExecutionResult:
        context = {"patient_id": self.patient_id, "mock_user_id": self.mock_user_id, "authorization": self.authorization, "accept_language": "zh-TW", "request_id": _identifier("REQ")}
        if idempotency_key:
            context["idempotency_key"] = idempotency_key
        try:
            result = self.pipeline.dispatch(ToolCall(name, {"context": context, "input": deepcopy(dict(input_data))}, call_id))
            if not isinstance(result, ToolExecutionResult):
                raise ValueError("invalid execution result")
        except Exception:
            result = ToolExecutionResult(name, call_id, False, context["request_id"], error={"code": "DISPATCH_OUTCOME_UNKNOWN", "message": "Tool dispatch did not return a verifiable result.", "retryable": False})
        logs.append({"type": "tool_execution", "tool": name, "ok": result.ok, "call_id": call_id})
        return result

    @staticmethod
    def _ambiguous(error: Mapping[str, Any]) -> bool:
        code = str(error.get("code", ""))
        status = error.get("status")
        definitive_rejections = {
            "SLOT_NOT_AVAILABLE", "SLOT_NOT_FOUND", "DUPLICATE_BOOKING", "CONSENT_REQUIRED",
            "PATIENT_CONTEXT_MISMATCH", "DEPARTMENT_NOT_FOUND", "DOCTOR_NOT_FOUND",
            "BOOKING_WINDOW_EXCEEDED", "INVALID_REQUEST", "MISSING_REQUIRED_FIELD",
            "UNAUTHORIZED", "FORBIDDEN", "INVALID_TOOL_ARGUMENTS", "UNKNOWN_TOOL",
            "PATIENT_CONTEXT_REQUIRED",
        }
        return code not in definitive_rejections or isinstance(status, int) and status >= 500

    def _verify_receipt(self, state: _TaskState, proposal: DemoProposal, result: ToolExecutionResult) -> tuple[dict[str, Any], dict[str, Any]]:
        if result.tool_name != CREATE or result.step_id != proposal.call_id or not isinstance(result.data, Mapping):
            raise ValueError("receipt belongs to another execution")
        payload = result.data
        appointment, backend_task, receipt = payload.get("data"), payload.get("task"), payload.get("receipt")
        if not all(isinstance(value, Mapping) for value in (appointment, backend_task, receipt)):
            raise ValueError("missing booking facts")
        frozen = proposal.frozen.tool_arguments()
        final_input, slot = frozen["input"], frozen["slot"]
        patient, department, location = appointment.get("patient"), appointment.get("department"), appointment.get("location")
        if not all(isinstance(value, Mapping) for value in (patient, department, location)):
            raise ValueError("missing booking identity")
        if (appointment.get("resourceType") != "Appointment" or appointment.get("status") != "booked"
                or patient.get("id") != self.patient_id or appointment.get("patient_id") != self.patient_id
                or department.get("id") != final_input["department_id"] or appointment.get("slot_id") != final_input["slot_id"]):
            raise ValueError("booking does not match approved input")
        start, expected_start = datetime.fromisoformat(appointment["start"]), datetime.fromisoformat(slot["start"])
        if start.tzinfo is None or start.utcoffset() is None or start != expected_start:
            raise ValueError("booking start does not match proposal")
        if final_input.get("doctor_id") and (not isinstance(appointment.get("doctor"), Mapping) or appointment["doctor"].get("id") != final_input["doctor_id"]):
            raise ValueError("booking doctor does not match proposal")
        appointment_id = _required(appointment.get("id"), "appointment.id")
        backend_task_id = _required(backend_task.get("id"), "task.id")
        if (backend_task.get("resourceType") != "Task" or backend_task.get("status") != "completed"
                or backend_task.get("patient_id") != self.patient_id or backend_task.get("appointment_id") != appointment_id
                or appointment.get("task_id") != backend_task_id or backend_task.get("business_type") != "medical_registration"):
            raise ValueError("backend task does not confirm this registration")
        reference = _required(receipt.get("reference"), "receipt.reference")
        if not re.fullmatch(r"MED-REG-[A-Za-z0-9][A-Za-z0-9-]*", reference):
            raise ValueError("invalid registration receipt reference")
        issued_at = _required(receipt.get("issued_at"), "receipt.issued_at")
        issued_time = datetime.fromisoformat(issued_at.replace("Z", "+00:00"))
        if issued_time.tzinfo is None or issued_time.utcoffset() is None:
            raise ValueError("invalid receipt issue time")
        public = {
            "appointment_id": appointment_id, "patient_id": self.patient_id, "department_id": department["id"],
            "slot_id": final_input["slot_id"], "start": appointment["start"], "status": "booked",
            "service": _required(department.get("display"), "department.display"),
            "date": start.astimezone(LOCAL_TZ).date().isoformat(), "time": start.astimezone(LOCAL_TZ).strftime("%H:%M"),
            "location": _required(location.get("display"), "location.display"), "backend_task_id": backend_task_id,
        }
        return public, {"receipt_id": reference, "kind": "medical_appointment", "status": "completed", "issued_at": issued_at,
                        "task_id": state.task["task_id"], "backend_task_id": backend_task_id, "appointment": deepcopy(public)}

    def _patient_blocked(self) -> bool:
        with self._patient_guard:
            return self.patient_id in self._blocked_patients

    def _uncertain(self, state: _TaskState, envelope: EventEnvelope, logs: list[dict[str, Any]], cause: str) -> WorkflowResult:
        with self._patient_guard:
            self._blocked_patients.add(self.patient_id)
        if state.pending_id:
            self._close_pending(state, "OUTCOME_NEEDS_CHECKING", "Patient is blocked pending manual verification.")
        state.task["facts"]["outcome_needs_checking"] = True
        return self._pause(state, envelope, logs, "outcome_needs_checking", "掛號結果需要人工查核。此示範病人的新掛號已封鎖；不會自動重試或更換掛號識別碼。請由操作員檢查後端紀錄，重新啟動不代表未曾掛號。", cause=cause)

    def _pause(self, state: _TaskState, envelope: EventEnvelope, logs: list[dict[str, Any]], reason: str, message: str, *, cause: str | None = None) -> WorkflowResult:
        state.task.update({"status": "awaiting_input", "current_step": "manual_review" if reason == "outcome_needs_checking" else "agent_paused"})
        state.task["recovery"] = {"reason": reason, "message": message, "allowed_actions": []}
        if cause:
            state.task["recovery"]["cause"] = cause
        logs.append({"type": "demo_paused", "reason": reason})
        return self._outcome(state, envelope, "recovery", logs)

    @staticmethod
    def _slot_details(state: _TaskState, slot: Mapping[str, Any]) -> dict[str, Any]:
        start = datetime.fromisoformat(slot["start"]).astimezone(LOCAL_TZ)
        location = slot.get("location")
        return {"service": state.departments["DEPT-CARDIO"].get("name", "心臟科"), "date": start.date().isoformat(), "time": start.strftime("%H:%M"), "location": deepcopy(location) if isinstance(location, Mapping) else {"display": "第一門診"}}

    def _outcome(self, state: _TaskState, envelope: EventEnvelope, intent: str, logs: list[dict[str, Any]]) -> WorkflowResult:
        task = deepcopy(state.task)
        actions: list[dict[str, Any]] = []
        if state.phase == "inquiry" and state.resume_action:
            actions = [{"label": "返回原預約", "event": deepcopy(state.resume_action)}]
        if state.pending_id:
            proposal = state.proposals[state.pending_id]
            labels = {"approve": "確認掛號", "reject": "取消掛號", "modify": "修改時段"}
            actions = [{"label": labels[decision], "event": {"type": "confirmation_decision", "action_id": action_id,
                        "task_id": proposal.task_id, "confirmation_id": proposal.frozen.proposal_id, "candidate_id": state.task["facts"]["candidate_id"], "decision": decision}}
                       for decision, action_id in proposal.actions]
        result = CanonicalInteractionResult(envelope.interaction_id, task, intent, deepcopy(task["facts"]), actions,
                                            deepcopy(task["pending_confirmation"]), deepcopy(task["recovery"]), deepcopy(task["receipt"]))
        return task, result, deepcopy(logs)
