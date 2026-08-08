"""Demo model wire aliases and disclosed deterministic rehearsal client.

The scripted client selects tools from the same transcript as the real model
and runs through the actual workflow, MCP and backend. Scripted runs do not
constitute real-model validation.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from datetime import datetime
import json
import re
from typing import Any
from types import MappingProxyType
import uuid

from .demo_medical_workflow import LOCAL_TZ, after_three
from .llm_transport import ChatCompletionClient


# OpenAI function names cannot contain a dot. These are wire aliases only;
# registry dispatch, proposals and the authoritative transcript retain MCP names.
MODEL_TOOL_ALIASES = MappingProxyType({
    "medical.list_departments": "medical_list_departments",
    "medical.search_registration_slots": "medical_search_registration_slots",
    "medical.create_registration": "medical_create_registration",
})
_REGISTRY_NAMES = {wire: registry for registry, wire in MODEL_TOOL_ALIASES.items()}


class RegistryToolNameClient:
    """Translate only the demo's three tool names at the real-model boundary.

    Native tool call IDs, arguments, call counts and result pairing are preserved.
    Unknown names stay unknown so the workflow's allowlist rejects them.
    """

    def __init__(self, client: ChatCompletionClient) -> None:
        self.client = client
        self.mode = getattr(client, "mode", "real")

    def complete(self, messages: Sequence[Mapping[str, Any]], **options: Any) -> Mapping[str, Any]:
        wire_messages = deepcopy(list(messages))
        for message in wire_messages:
            if message.get("role") in {"system", "developer"} and isinstance(message.get("content"), str):
                # Only instructions are rewritten; user text and backend results
                # remain verbatim. Include the prompt's short operation names.
                for registry_name, wire_name in MODEL_TOOL_ALIASES.items():
                    short_name = registry_name.split(".", 1)[1]
                    message["content"] = re.sub(
                        rf"(?<![\w.])(?:{re.escape(registry_name)}|{re.escape(short_name)})(?!\w|\.\w)",
                        wire_name, message["content"],
                    )
            if message.get("role") == "assistant":
                self._native_calls(message, MODEL_TOOL_ALIASES)
        wire_options = deepcopy(options)
        for tool in wire_options.get("tools", []):
            function = tool.get("function")
            if isinstance(function, dict) and function.get("name") in MODEL_TOOL_ALIASES:
                function["name"] = MODEL_TOOL_ALIASES[function["name"]]
        choice = wire_options.get("tool_choice")
        if isinstance(choice, dict) and isinstance(choice.get("function"), dict):
            name = choice["function"].get("name")
            if name in MODEL_TOOL_ALIASES:
                choice["function"]["name"] = MODEL_TOOL_ALIASES[name]
        response = deepcopy(dict(self.client.complete(wire_messages, **wire_options)))
        self._json_action(response)
        for choice in response.get("choices", []):
            if not isinstance(choice, Mapping) or not isinstance(choice.get("message"), dict):
                continue
            message = choice["message"]
            self._native_calls(message, _REGISTRY_NAMES)
            content = message.get("content")
            if isinstance(content, str):
                try:
                    action = json.loads(content)
                except json.JSONDecodeError:
                    continue
                if isinstance(action, dict) and self._json_action(action):
                    message["content"] = json.dumps(action, ensure_ascii=False)
        return response

    @staticmethod
    def _native_calls(message: dict[str, Any], names: Mapping[str, str]) -> None:
        calls = message.get("tool_calls")
        if not isinstance(calls, list):
            return
        for call in calls:
            function = call.get("function") if isinstance(call, Mapping) else None
            if isinstance(function, dict) and isinstance(function.get("name"), str) and function["name"] in names:
                function["name"] = names[function["name"]]

    @staticmethod
    def _json_action(action: dict[str, Any]) -> bool:
        name = action.get("tool_name")
        if action.get("action") == "tool_call" and isinstance(name, str) and name in _REGISTRY_NAMES:
            action["tool_name"] = _REGISTRY_NAMES[name]
            return True
        return False


class ScriptedCardiologyClient:
    mode = "scripted"

    def complete(self, messages: Sequence[Mapping[str, Any]], **options: Any) -> Mapping[str, Any]:
        del options
        context = json.loads(str(messages[0]["content"]).split("DEMO_SERVER_CONTEXT=", 1)[1])
        calls: dict[str, str] = {}
        last_user = max(index for index, message in enumerate(messages) if message.get("role") == "user")
        minimum_after_three = False
        for message in messages:
            if message.get("role") == "user":
                content = str(message.get("content", ""))
                if after_three(content):
                    minimum_after_three = True
                elif any(word in content.casefold() for word in ("afternoon", "下午", "14:00", "2 pm", "兩點", "两点")):
                    minimum_after_three = False
        department_seen = False
        search_index = -1
        failed_create_index = -1
        slots: list[Mapping[str, Any]] = []
        for index, message in enumerate(messages):
            if message.get("role") == "assistant":
                for call in message.get("tool_calls", []):
                    calls[call["id"]] = call["function"]["name"]
            if message.get("role") != "tool":
                continue
            result = json.loads(str(message["content"]))
            name = calls.get(str(message.get("tool_call_id")))
            if name == "medical.list_departments" and result.get("ok"):
                department_seen = True
            if name == "medical.search_registration_slots" and result.get("ok"):
                search_index = index
                slots = result["data"]["data"]
            if name == "medical.create_registration" and not result.get("ok"):
                failed_create_index = index
        if not department_seen:
            return self._call("medical.list_departments", {"keyword": "Cardiology", "active_only": True})
        if search_index < max(last_user, failed_create_index):
            return self._call("medical.search_registration_slots", {"department_id": "DEPT-CARDIO", "date": context["next_tuesday"], "session": "afternoon"})
        eligible = []
        for slot in slots:
            start = datetime.fromisoformat(slot["start"]).astimezone(LOCAL_TZ)
            if slot.get("remaining", 0) > 0 and slot.get("status") == "free" and (not minimum_after_three or start.hour * 60 + start.minute > 15 * 60):
                eligible.append(slot)
        if not eligible:
            return {"choices": [{"message": {"role": "assistant", "content": json.dumps({"action": "clarify", "message": "No available cardiology slot matches the requested time."})}}]}
        slot = min(eligible, key=lambda item: datetime.fromisoformat(item["start"]))
        arguments = {"department_id": "DEPT-CARDIO", "slot_id": slot["id"], "consent": True}
        if slot.get("doctor_id"):
            arguments["doctor_id"] = slot["doctor_id"]
        return self._call("medical.create_registration", arguments)

    @staticmethod
    def _call(name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [{
            "id": f"scripted-{uuid.uuid4().hex}", "type": "function",
            "function": {"name": name, "arguments": json.dumps(deepcopy(dict(arguments)))},
        }]}}]}
