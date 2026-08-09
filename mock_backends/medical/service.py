"""Administrative medical booking operations."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from threading import RLock
from typing import Any, Callable

from mock_backends.core.contracts import Clock, IdGenerator, IdempotencyStore, RecordRepository
from mock_backends.core.errors import DomainError
from mock_backends.core.http import BackendResponse, success_body
from mock_backends.core.idempotency import canonical_json_hash

from .contracts import required_body, required_idempotency_key
from .fixtures import appointment_services, appointment_slots, departments, doctors, next_tuesday, registration_slots
from .demo_profile import PROFILE_NAME, build_demo_catalogue, registration_slots_for_date, appointment_slots_for_date


# Covers the entire write/replay sequence, including services sharing a repository
# in this process. JSON writes remain separate and are not crash-atomic.
_MEDICAL_WRITE_LOCK = RLock()


class MedicalService:
    def __init__(
        self,
        clock: Clock,
        ids: IdGenerator,
        appointment_repository: RecordRepository,
        task_repository: RecordRepository,
        idempotency: IdempotencyStore,
        rolling_slots: bool = False,
        appointment_slot_reference_date: date | None = None,
        registration_slot_reference_date: date | None = None,
        medical_data_profile: str = "legacy",
    ) -> None:
        if medical_data_profile not in {"legacy", PROFILE_NAME}:
            raise ValueError("unknown medical data profile")
        self.clock = clock
        self.ids = ids
        self.appointment_repository = appointment_repository
        self.task_repository = task_repository
        self.idempotency = idempotency
        self.rolling_slots = rolling_slots
        self.appointment_slot_reference_date = appointment_slot_reference_date
        self.registration_slot_reference_date = registration_slot_reference_date or next_tuesday(clock.now().date())
        self.medical_data_profile = medical_data_profile

    def _departments(self) -> list[dict]:
        return build_demo_catalogue(self.clock.now().date())["departments"] if self.medical_data_profile == PROFILE_NAME else departments()

    def _doctors(self) -> list[dict]:
        return build_demo_catalogue(self.clock.now().date())["doctors"] if self.medical_data_profile == PROFILE_NAME else doctors()

    def _services(self) -> list[dict]:
        return build_demo_catalogue(self.clock.now().date())["appointment_services"] if self.medical_data_profile == PROFILE_NAME else appointment_services()

    def _registration_inventory(self, selected_date: date | None = None) -> list[dict]:
        if self.medical_data_profile != PROFILE_NAME:
            if self.rolling_slots:
                return registration_slots(self.registration_slot_reference_date, now=self.clock.now())
            return registration_slots(self.registration_slot_reference_date)
        today = self.clock.now().date()
        days = [selected_date] if selected_date else [today + timedelta(days=i) for i in range(15)]
        return [slot for day in days for slot in registration_slots_for_date(day)]

    def _appointment_inventory(self) -> list[dict]:
        if self.medical_data_profile != PROFILE_NAME:
            if self.rolling_slots:
                return appointment_slots(self.appointment_slot_reference_date, now=self.clock.now())
            return appointment_slots(self.appointment_slot_reference_date)
        today = self.clock.now().date()
        return [slot for offset in range(15) for slot in appointment_slots_for_date(today + timedelta(days=offset))]

    @staticmethod
    def _occupies_capacity(record: dict[str, Any]) -> bool:
        # Unknown status remains conservative; terminal/cancelled history is not inventory.
        return str(record.get("status", "")).lower() not in {
            "cancelled", "canceled", "entered-in-error", "noshow", "no-show", "fulfilled", "completed",
        }

    def _effective_slot(self, base: dict[str, Any]) -> dict[str, Any]:
        item = deepcopy(base)
        used = len(self.appointment_repository.find(lambda record: record.get("slot_id") == item["id"] and self._occupies_capacity(record)))
        item["remaining"] = max(0, item["remaining"] - used)
        if item["remaining"] == 0:
            item["status"] = "busy"
        return item

    def _future_live_slot(self, slot: dict[str, Any]) -> bool:
        return self.medical_data_profile != PROFILE_NAME or datetime.fromisoformat(slot["start"]) > self.clock.now()

    def _validate_live_slot_time(self, slot: dict[str, Any]) -> None:
        if self.medical_data_profile == PROFILE_NAME:
            self._within_window(date.fromisoformat(slot["start"][:10]))
            if not self._future_live_slot(slot):
                raise DomainError(409, "SLOT_EXPIRED", "所選時段已過期，請重新查詢。")

    def _response(self, request_id: str, status: int, data: Any, meta: dict[str, Any] | None = None) -> BackendResponse:
        body = success_body(request_id, data)
        if self.medical_data_profile == PROFILE_NAME:
            meta = {**(meta or {}), "data_profile": PROFILE_NAME, "synthetic": True}
        if meta is not None:
            body["meta"] = meta
        return BackendResponse(status, body)

    @staticmethod
    def _saved_response(saved: dict[str, Any]) -> BackendResponse:
        response = saved["response"]
        return BackendResponse(response["status"], deepcopy(response["body"]), deepcopy(response.get("headers", {"Content-Type": "application/json"})))

    def _idempotent(
        self,
        patient_id: str,
        path: str,
        headers: dict[str, str],
        body: dict[str, Any],
        operation: Callable[[], BackendResponse],
    ) -> BackendResponse:
        with _MEDICAL_WRITE_LOCK:
            key = required_idempotency_key(headers)
            scope = f"{patient_id}:{path}"
            request_hash = canonical_json_hash(body)
            saved = self.idempotency.lookup(scope, key)
            if saved is not None:
                self.idempotency.remember(scope, key, request_hash, saved["response"])
                return self._saved_response(saved)
            response = operation()
            self.idempotency.remember(scope, key, request_hash, {"status": response.status, "body": response.body, "headers": response.headers})
            return response

    @staticmethod
    def _value(query: dict[str, list[str]], name: str, default: str = "") -> str:
        value = query.get(name, [default])
        if isinstance(value, list):
            return value[0] if value else default
        return str(value)

    @staticmethod
    def _csv(query: dict[str, list[str]], name: str) -> set[str]:
        return {item.strip() for item in MedicalService._value(query, name).split(",") if item.strip()}

    def _within_window(self, value: date) -> None:
        today = self.clock.now().date()
        if value < today or value > today + timedelta(days=14):
            raise DomainError(422, "BOOKING_WINDOW_EXCEEDED", "日期超出 mock 預設 14 日預約窗口。")

    def list_departments(self, query: dict[str, list[str]], request_id: str) -> BackendResponse:
        keyword = self._value(query, "keyword").casefold()
        result = [item for item in self._departments() if item["active"] and (not keyword or keyword in f"{item['name']} {item['name_en']}".casefold())]
        return self._response(request_id, 200, result, {"total": len(result)})

    def list_department_doctors(self, department_id: str, request_id: str) -> BackendResponse:
        if not any(item["id"] == department_id and item["active"] for item in self._departments()):
            raise DomainError(404, "DEPARTMENT_NOT_FOUND", "科室不存在或已停用。")
        result = [item for item in self._doctors() if item["department_id"] == department_id and item["active"]]
        return self._response(request_id, 200, result, {"total": len(result)})

    def _registration_slot(self, slot_id: str) -> dict[str, Any] | None:
        for base in self._registration_inventory():
            if base["id"] == slot_id:
                return self._effective_slot(base)
        return None

    def _appointment_slot(self, slot_id: str) -> dict[str, Any] | None:
        for base in self._appointment_inventory():
            if base["id"] == slot_id:
                return self._effective_slot(base)
        return None

    def search_registration_slots(self, query: dict[str, list[str]], request_id: str) -> BackendResponse:
        department_id = self._value(query, "department_id")
        if not department_id:
            raise DomainError(400, "MISSING_REQUIRED_FIELD", "department_id 為必填欄位。")
        if not any(item["id"] == department_id and item["active"] for item in self._departments()):
            raise DomainError(404, "DEPARTMENT_NOT_FOUND", "科室不存在或已停用。")
        raw_date = self._value(query, "date")
        if not raw_date:
            raise DomainError(400, "MISSING_REQUIRED_FIELD", "date 為必填欄位。")
        try:
            selected_date = date.fromisoformat(raw_date)
        except ValueError as exc:
            raise DomainError(400, "INVALID_REQUEST", "date 必須是有效日期。") from exc
        self._within_window(selected_date)
        doctor_id = self._value(query, "doctor_id")
        session = self._value(query, "session")
        location_id = self._value(query, "location_id")
        result = []
        for base in self._registration_inventory(selected_date):
            item = self._effective_slot(base)
            if item["department_id"] != department_id or item["start"][:10] != raw_date:
                continue
            if doctor_id and item.get("doctor_id") != doctor_id:
                continue
            if session and item.get("session") != session:
                continue
            if location_id and item.get("location_id") != location_id:
                continue
            if item["remaining"] > 0 and item.get("status") == "free" and self._future_live_slot(item):
                result.append(item)
        result.sort(key=lambda item: (item["start"], item["id"]))
        return self._response(request_id, 200, result, {"total": len(result), "timezone": "Asia/Macau", "booking_window_days": 14})

    def _department(self, department_id: str) -> dict[str, Any]:
        for item in self._departments():
            if item["id"] == department_id and item["active"]:
                return item
        raise DomainError(404, "DEPARTMENT_NOT_FOUND", "科室不存在或已停用。")

    def _doctor(self, doctor_id: str, department_id: str) -> dict[str, Any]:
        for item in self._doctors():
            if item["id"] == doctor_id and item["department_id"] == department_id and item["active"]:
                return item
        raise DomainError(404, "DOCTOR_NOT_FOUND", "醫生不存在或不屬於指定科室。")

    def _task(self, patient_id: str, business_type: str, workflow_type: str, appointment_id: str, request_id: str) -> dict[str, Any]:
        task_id = self.ids.next("TASK")
        task = {
            "resourceType": "Task",
            "id": task_id,
            "patient_id": patient_id,
            "business_type": business_type,
            "status": "completed",
            "appointment_id": appointment_id,
            "workflow_type": workflow_type,
            "current_step": "complete",
            "events": [
                {"step_id": "validate_patient", "event_type": "validation_succeeded", "timestamp": self.clock.now().isoformat()},
                {"step_id": "submit_booking", "event_type": "booking_created", "timestamp": self.clock.now().isoformat()},
            ],
            "updated_at": self.clock.now().isoformat(),
        }
        self.task_repository.insert(task)
        return task

    def create_registration(self, patient_id: str, body: dict[str, Any] | None, headers: dict[str, str], request_id: str, path: str) -> BackendResponse:
        payload = required_body(body)

        def create() -> BackendResponse:
            if payload.get("patient_id") != patient_id:
                raise DomainError(403, "PATIENT_CONTEXT_MISMATCH", "body 的 patient_id 與 X-Patient-Id 不一致。")
            if payload.get("consent") is not True:
                raise DomainError(422, "CONSENT_REQUIRED", "consent 必須為 true。")
            department = self._department(payload.get("department_id", ""))
            doctor_id = payload.get("doctor_id")
            doctor = self._doctor(doctor_id, department["id"]) if doctor_id else None
            slot = self._registration_slot(payload.get("slot_id", ""))
            if slot is None:
                raise DomainError(404, "SLOT_NOT_FOUND", "時段不存在、已過期或不屬於指定服務。")
            if slot["department_id"] != department["id"] or (doctor_id and slot.get("doctor_id") != doctor_id):
                raise DomainError(404, "SLOT_NOT_FOUND", "時段不屬於指定科室或醫生。")
            self._validate_live_slot_time(slot)
            if doctor is None and slot.get("doctor_id"):
                doctor = self._doctor(slot["doctor_id"], department["id"])
            if slot["remaining"] <= 0:
                raise DomainError(409, "SLOT_NOT_AVAILABLE", "所選時段已被其他掛號佔用。")
            if self.appointment_repository.find(lambda record: record.get("patient_id") == patient_id and record.get("slot_id") == slot["id"] and self._occupies_capacity(record)):
                raise DomainError(409, "DUPLICATE_BOOKING", "同一病人已有衝突的有效掛號。")
            appointment_id = self.ids.next("APT")
            created_at = self.clock.now().isoformat()
            appointment = {
                "resourceType": "Appointment",
                "id": appointment_id,
                "status": "booked",
                "appointment_type": "outpatient_registration",
                "registration_number": f"A{self.ids.next('REGNO').split('-')[-1]}",
                "patient": {"id": patient_id, "display": "陳先生"},
                "patient_id": patient_id,
                "department": {"id": department["id"], "display": department["name"]},
                "doctor": {"id": doctor["id"], "display": doctor["name"]} if doctor else None,
                "location": deepcopy(slot.get("location") or {"id": slot["location_id"], "display": "第一門診"}),
                "start": slot["start"],
                "end": slot["end"],
                "slot_id": slot["id"],
                "booking_source": "ponte_mock",
                "created_at": created_at,
                "instructions": deepcopy(slot.get("instructions") or ["請於預約時間前到科室接待處報到"]),
            }
            if self.medical_data_profile == PROFILE_NAME:
                appointment.update(synthetic=True)
                appointment["patient"]["display"] = "陳先生（模擬病人）"
            task = self._task(patient_id, "medical_registration", "medical_registration_v1", appointment_id, request_id)
            appointment["task_id"] = task["id"]
            self.appointment_repository.insert(appointment)
            return BackendResponse(
                201,
                {
                    "request_id": request_id,
                    "data": appointment,
                    "task": task,
                    "receipt": {"reference": self.ids.next("MED-REG"), "issued_at": created_at},
                },
            )

        return self._idempotent(patient_id, path, headers, payload, create)

    def list_appointment_services(self, query: dict[str, list[str]], request_id: str) -> BackendResponse:
        department_id = self._value(query, "department_id")
        service_type = self._value(query, "type")
        keyword = self._value(query, "keyword").casefold()
        active_only = self._value(query, "active_only", "true").lower() != "false"
        available_only = self._value(query, "available_only", "true").lower() != "false"
        result = []
        for item in self._services():
            if active_only and not item["active"]:
                continue
            if department_id and item["department_id"] != department_id:
                continue
            if service_type and item["type"] != service_type:
                continue
            if keyword and keyword not in f"{item['name']} {item['name_en']}".casefold():
                continue
            if available_only and not self._has_available_appointment_slot(item["id"]):
                continue
            result.append(item)
        return self._response(request_id, 200, result, {"total": len(result)})

    def _has_available_appointment_slot(self, service_id: str) -> bool:
        today = self.clock.now().date()
        latest = today + timedelta(days=14)
        for base in self._appointment_inventory():
            item = self._effective_slot(base)
            slot_date = date.fromisoformat(item["start"][:10])
            if (
                item["service_id"] == service_id
                and today <= slot_date <= latest
                and item["remaining"] > 0
                and self._future_live_slot(item)
            ):
                return True
        return False

    def _service(self, service_id: str) -> dict[str, Any]:
        for item in self._services():
            if item["id"] == service_id and item["active"]:
                return item
        raise DomainError(404, "SERVICE_NOT_FOUND", "檢查或治療服務不存在。")

    def search_appointment_slots(self, query: dict[str, list[str]], request_id: str) -> BackendResponse:
        service = self._service(self._value(query, "service_id"))
        raw_from = self._value(query, "date_from")
        raw_to = self._value(query, "date_to")
        if not raw_from or not raw_to:
            raise DomainError(400, "MISSING_REQUIRED_FIELD", "date_from 和 date_to 為必填欄位。")
        try:
            date_from = date.fromisoformat(raw_from)
            date_to = date.fromisoformat(raw_to)
        except ValueError as exc:
            raise DomainError(400, "INVALID_REQUEST", "date_from/date_to 必須是有效日期。") from exc
        self._within_window(date_from)
        self._within_window(date_to)
        if date_to < date_from or date_to - date_from > timedelta(days=14):
            raise DomainError(422, "BOOKING_WINDOW_EXCEEDED", "查詢時段範圍不可超過 14 日。")
        doctor_id = self._value(query, "doctor_id")
        location_id = self._value(query, "location_id")
        result = []
        for base in self._appointment_inventory():
            item = self._effective_slot(base)
            if item["service_id"] != service["id"] or not (date_from <= date.fromisoformat(item["start"][:10]) <= date_to):
                continue
            if doctor_id and item.get("doctor_id") != doctor_id:
                continue
            if location_id and item.get("location_id") != location_id:
                continue
            if item["remaining"] > 0 and item.get("status") == "free" and self._future_live_slot(item):
                result.append(item)
        result.sort(key=lambda item: (item["start"], item["id"]))
        return self._response(request_id, 200, result, {"total": len(result), "timezone": "Asia/Macau", "booking_window_days": 14})

    def create_appointment(self, patient_id: str, body: dict[str, Any] | None, headers: dict[str, str], request_id: str, path: str) -> BackendResponse:
        payload = required_body(body)

        def create() -> BackendResponse:
            if payload.get("patient_id") != patient_id:
                raise DomainError(403, "PATIENT_CONTEXT_MISMATCH", "body 的 patient_id 與 X-Patient-Id 不一致。")
            if payload.get("consent") is not True:
                raise DomainError(422, "CONSENT_REQUIRED", "consent 必須為 true。")
            service = self._service(payload.get("service_id", ""))
            referral = payload.get("referring_appointment_id")
            if service["requires_referral"] and not referral:
                raise DomainError(422, "REFERRAL_REQUIRED", "該檢查／治療需要關聯門診或轉介資料。")
            slot = self._appointment_slot(payload.get("slot_id", ""))
            if slot is None or slot.get("service_id") != service["id"]:
                raise DomainError(404, "SLOT_NOT_FOUND", "時段不存在、已過期或不屬於指定服務。")
            self._validate_live_slot_time(slot)
            if slot["remaining"] <= 0:
                raise DomainError(409, "SLOT_NOT_AVAILABLE", "所選時段已被其他預約佔用。")
            if self.appointment_repository.find(lambda record: record.get("patient_id") == patient_id and record.get("slot_id") == slot["id"] and self._occupies_capacity(record)):
                raise DomainError(409, "DUPLICATE_BOOKING", "同一病人已有衝突的有效預約。")
            appointment_id = self.ids.next("APT")
            created_at = self.clock.now().isoformat()
            department = next(item for item in self._departments() if item["id"] == service["department_id"])
            appointment = {
                "resourceType": "Appointment",
                "id": appointment_id,
                "status": "confirmed",
                "appointment_type": service["type"],
                "patient": {"id": patient_id, "display": "陳先生"},
                "patient_id": patient_id,
                "service": {"id": service["id"], "display": service["name"]},
                "department": {"id": department["id"], "display": department["name"]},
                "location": deepcopy(slot["location"]),
                "start": slot["start"],
                "end": slot["end"],
                "slot_id": slot["id"],
                "booking_source": "ponte_mock",
                "created_at": created_at,
                "instructions": ["請攜帶有效身份證明", "請於預約時間前 15 分鐘報到"],
            }
            if self.medical_data_profile == PROFILE_NAME:
                appointment.update(synthetic=True, instructions=deepcopy(slot["instructions"]), doctor=deepcopy(slot.get("doctor")))
                appointment["patient"]["display"] = "陳先生（模擬病人）"
            task = self._task(patient_id, "medical_appointment", "medical_appointment_v1", appointment_id, request_id)
            appointment["task_id"] = task["id"]
            self.appointment_repository.insert(appointment)
            return BackendResponse(
                201,
                {"request_id": request_id, "data": appointment, "task": task, "receipt": {"reference": self.ids.next("MED-APT"), "issued_at": created_at}},
            )

        return self._idempotent(patient_id, path, headers, payload, create)

    @staticmethod
    def _public_appointment(record: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(record)
        result.pop("patient_id", None)
        result.pop("slot_id", None)
        return result

    def list_appointments(self, patient_id: str, query: dict[str, list[str]], request_id: str) -> BackendResponse:
        result = [self._public_appointment(item) for item in self.appointment_repository.find(lambda record: record.get("patient_id") == patient_id)]
        statuses = self._csv(query, "status")
        if statuses:
            result = [item for item in result if item.get("status") in statuses]
        appointment_type = self._value(query, "appointment_type")
        if appointment_type:
            result = [item for item in result if item.get("appointment_type") == appointment_type]
        date_from = self._value(query, "date_from")
        date_to = self._value(query, "date_to")
        if date_from:
            result = [item for item in result if item["start"][:10] >= date_from]
        if date_to:
            result = [item for item in result if item["start"][:10] <= date_to]
        try:
            page = int(self._value(query, "page", "1"))
            page_size = int(self._value(query, "page_size", "20"))
        except ValueError as exc:
            raise DomainError(400, "INVALID_REQUEST", "page/page_size 必須是整數。") from exc
        if page < 1 or page_size < 1 or page_size > 100:
            raise DomainError(400, "INVALID_REQUEST", "page/page_size 超出有效範圍。")
        total = len(result)
        start = (page - 1) * page_size
        return self._response(request_id, 200, result[start:start + page_size], {"page": page, "page_size": page_size, "total": total, "has_next": start + page_size < total})

    def get_appointment(self, patient_id: str, appointment_id: str, request_id: str) -> BackendResponse:
        record = self.appointment_repository.get(appointment_id)
        if record is None or record.get("patient_id") != patient_id:
            raise DomainError(404, "APPOINTMENT_NOT_FOUND", "預約不存在或不屬於當前病人。")
        return self._response(request_id, 200, self._public_appointment(record))

    def get_task(self, patient_id: str, task_id: str, request_id: str) -> BackendResponse:
        record = self.task_repository.get(task_id)
        if record is None or record.get("patient_id") != patient_id:
            raise DomainError(404, "TASK_NOT_FOUND", "任務不存在或不屬於當前病人。")
        result = deepcopy(record)
        result.pop("patient_id", None)
        return self._response(request_id, 200, result)
