"""Task-oriented interaction routing independent of domain workflow details."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from threading import Lock, RLock
from typing import Any

from .intent import IntentDecision, IntentRecognizer, KeywordIntentRecognizer, build_intent_recognizer
from .interaction_contracts import CanonicalInteractionResult, EventEnvelope
from .medical_workflow import MedicalWorkflow, WorkflowResult
from .session import SessionState, SessionStore


class InteractionCore:
    """Load one active task, select its workflow, and persist its result."""

    def __init__(
        self,
        sessions: SessionStore,
        medical_workflow: MedicalWorkflow,
        *,
        intent_recognizer: IntentRecognizer | None = None,
        cash_workflow: Any | None = None,
        demo_workflow: Any | None = None,
    ) -> None:
        self.sessions = sessions
        self.medical_workflow = medical_workflow
        self.cash_workflow = cash_workflow
        self.demo_workflow = demo_workflow
        self.intent_recognizer = intent_recognizer or build_intent_recognizer()
        self._session_locks: dict[str, Any] = {}
        self._locks_guard = Lock()

    def handle(self, envelope: EventEnvelope) -> CanonicalInteractionResult:
        if not isinstance(envelope, EventEnvelope):
            raise ValueError("envelope must be an EventEnvelope")
        with self._locks_guard:
            turn_lock = self._session_locks.setdefault(envelope.session_id, RLock())
        # Load, decide, dispatch and save are one turn. A browser abort does not
        # release this lock or cancel a transaction already submitted.
        with turn_lock:
            state = self.sessions.get_or_create(envelope.session_id)
            if envelope.event.get("type") == "user_utterance":
                outcome = self._handle_utterance(state, envelope)
            else:
                task = self._active_task(state)
                outcome = self._workflow_for_task(task).handle(deepcopy(task), envelope)
            return self._save(state, outcome)

    def _handle_utterance(self, state: SessionState, envelope: EventEnvelope) -> WorkflowResult:
        task = state.task
        if isinstance(task, Mapping) and task.get("status") not in {"completed", "cancelled", "failed"}:
            return self._workflow_for_task(task).handle(deepcopy(dict(task)), envelope)
        content = envelope.event.get("content")
        if not isinstance(content, str) or not content.strip():
            raise ValueError("event.content must be a non-empty string")
        # The explicit demo entry avoids relying on legacy intent classification
        # for an utterance such as "心臟科下週二下午". Queries keep their old path.
        if isinstance(task, Mapping) and task.get("type") == "medical_demo_agent":
            # A change that arrived after submission observes the completed or
            # uncertain transaction before another task can be started.
            if self._is_demo_followup(content):
                return self.demo_workflow.handle(deepcopy(dict(task)), envelope)
        if self.demo_workflow is not None and self._is_demo_request(content):
            return self.demo_workflow.start(envelope, IntentDecision("medical_booking", "keyword", 1.0))
        decision = self.intent_recognizer.recognize(content.strip())
        return self._workflow_for_intent(decision).start(envelope, decision)

    @staticmethod
    def _is_demo_followup(content: str) -> bool:
        text = content.casefold()
        if any(term in text for term in KeywordIntentRecognizer.DEFAULT_MEDICAL_QUERY_TERMS):
            return False
        if any(term in text for term in (
            "查詢", "查询", "現金分享", "cash sharing", "檢查", "检查", "超聲波", "超声波", "治療", "治疗",
        )):
            return False
        return any(term in text for term in (
            "心臟科", "心脏科", "cardiology", "改", "取消", "下午", "after", "cancel", "yes", "確認", "确认",
        ))

    @staticmethod
    def _is_demo_request(content: str) -> bool:
        text = content.casefold()
        if any(term in text for term in KeywordIntentRecognizer.DEFAULT_MEDICAL_QUERY_TERMS):
            return False
        return any(term in text for term in ("心臟科", "心脏科", "cardiology")) and not any(
            term in text for term in (
                "查詢", "查询", "紀錄", "記錄", "记录", "my appointments",
                "檢查", "检查", "超聲波", "超声波", "治療", "治疗", "examination", "ultrasound",
            )
        )

    def _workflow_for_intent(self, decision: IntentDecision) -> Any:
        if decision.is_medical:
            return self.medical_workflow
        if decision.is_cash_sharing and self.cash_workflow is not None:
            return self.cash_workflow
        raise ValueError("unsupported interaction intent")

    def _workflow_for_task(self, task: Mapping[str, Any]) -> Any:
        task_type = task.get("type")
        if task_type == "medical_demo_agent" and self.demo_workflow is not None:
            return self.demo_workflow
        if task_type == "medical_appointment":
            return self.medical_workflow
        if task_type == "cash_sharing_query" and self.cash_workflow is not None:
            return self.cash_workflow
        raise ValueError("unsupported task type")

    @staticmethod
    def _active_task(state: SessionState) -> dict[str, Any]:
        if not isinstance(state.task, dict):
            raise ValueError("task does not exist")
        return state.task

    def _save(self, state: SessionState, outcome: WorkflowResult) -> CanonicalInteractionResult:
        task, result, log_entries = outcome
        if not isinstance(task, dict) or not isinstance(result, CanonicalInteractionResult):
            raise ValueError("workflow returned an invalid result")
        state.active_task_id = task.get("task_id")
        state.task = deepcopy(task)
        state.interaction_log.extend(deepcopy(log_entries))
        self.sessions.save(state)
        return result
