"""Synthetic, date-stable medical inventory for the opt-in live demonstration.

The original fixtures remain the regression/evaluation contract.  This module
only builds fresh dictionaries; application composition owns persistence,
capacity deductions, the booking window, and deciding which dates to expose.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, time, timedelta, timezone
from hashlib import sha256

from .fixtures import (
    LOCATION_DISPLAYS,
    appointment_services,
    departments,
    doctors,
    next_tuesday,
)


PROFILE_NAME = "live-demo-v2"
TIMEZONE_NAME = "Asia/Macau"
LOCAL_TZ = timezone(timedelta(hours=8))

_DOCTOR_NAMES = {
    "DOC-001": "陳醫生（模擬）",
    "DOC-002": "李醫生（模擬）",
    "DOC-003": "周醫生（模擬）",
}
_SERVICE_TIMES = {
    "SERVICE-US-001": ("US", (time(9, 30), time(14, 45))),
    "SERVICE-PT-001": ("PT", (time(10, 0), time(14, 0))),
    "SERVICE-ECHO-001": ("ECHO", (time(9, 0), time(16, 0))),
}
_PATIENT_DISPLAY = "陳先生（模擬病人）"


def _location(location_id: str) -> dict:
    return {"id": location_id, "display": LOCATION_DISPLAYS[location_id]}


def _period(day: date, start_time: time, duration: int) -> tuple[str, str]:
    start = datetime.combine(day, start_time, tzinfo=LOCAL_TZ)
    return start.isoformat(), (start + timedelta(minutes=duration)).isoformat()


def _instructions(*, referral: bool = False) -> list[str]:
    instructions = [
        "本資料只供 Ponte 模擬示範，並非真實醫院預約。",
        "請攜帶有效身份證明，於預約前 15 分鐘到接待處報到。",
    ]
    if referral:
        instructions.append("請攜帶轉介資料；檢查或治療準備以院方正式通知為準。")
    return instructions


def build_demo_catalogue(reference_date: date) -> dict:
    """Return independent catalogue records without changing the legacy data."""
    department_records = departments()
    doctor_records = doctors()
    service_records = appointment_services()
    department_locations = {item["id"]: item["location_id"] for item in department_records}
    for item in department_records:
        item.update(
            location=_location(item["location_id"]),
            description=f"Ponte 模擬醫療服務：{item['name']}；非真實醫院資料。",
            synthetic=True,
        )
    for item in doctor_records:
        item.update(
            name=_DOCTOR_NAMES[item["id"]],
            display=_DOCTOR_NAMES[item["id"]],
            location=_location(department_locations[item["department_id"]]),
            synthetic=True,
        )
    for item in service_records:
        item.update(
            description=f"{item['name']}，預計 {item['duration_minutes']} 分鐘；模擬資料。",
            instructions=_instructions(referral=item["requires_referral"]),
            synthetic=True,
        )
    return {
        "profile": PROFILE_NAME,
        "reference_date": reference_date.isoformat(),
        "timezone": TIMEZONE_NAME,
        "departments": department_records,
        "doctors": doctor_records,
        "appointment_services": service_records,
    }


def registration_slots_for_date(day: date) -> list[dict]:
    """Build weekday cardiology slots with stable date-derived identifiers."""
    if day.weekday() >= 5:
        return []
    result = []
    for start_time in (time(9), time(10, 30), time(14), time(15), time(15, 15), time(15, 30), time(16)):
        start, end = _period(day, start_time, 15)
        full = start_time == time(15, 15)
        doctor_id = "DOC-001" if start_time.hour < 12 else "DOC-002"
        result.append({
            "resourceType": "Slot",
            "id": f"SLOT-LIVE-V2-REG-{day:%Y%m%d}-CARDIO-{start_time:%H%M}",
            "status": "busy" if full else "free",
            "slot_type": "outpatient_registration",
            "department_id": "DEPT-CARDIO",
            "doctor_id": doctor_id,
            "doctor": {"id": doctor_id, "display": _DOCTOR_NAMES[doctor_id]},
            "location_id": "LOC-MAIN-OPD",
            "location": _location("LOC-MAIN-OPD"),
            "start": start,
            "end": end,
            "capacity": 1,
            "remaining": 0 if full else 1,
            "session": "morning" if start_time.hour < 12 else "afternoon",
            "instructions": _instructions(),
            "synthetic": True,
        })
    return result


def appointment_slots_for_date(day: date) -> list[dict]:
    """Build two weekday slots per existing examination/treatment service."""
    if day.weekday() >= 5:
        return []
    result = []
    for service in appointment_services():
        code, start_times = _SERVICE_TIMES[service["id"]]
        for start_time in start_times:
            start, end = _period(day, start_time, service["duration_minutes"])
            item = {
                "resourceType": "Slot",
                "id": f"SLOT-LIVE-V2-APT-{day:%Y%m%d}-{code}-{start_time:%H%M}",
                "status": "free",
                "slot_type": service["type"],
                "service_id": service["id"],
                "department_id": service["department_id"],
                "location_id": service["location_id"],
                "location": deepcopy(service["location"]),
                "start": start,
                "end": end,
                "capacity": 1,
                "remaining": 1,
                "requires_referral": service["requires_referral"],
                "instructions": _instructions(referral=service["requires_referral"]),
                "synthetic": True,
            }
            if service["id"] == "SERVICE-PT-001":
                item.update(doctor_id="DOC-003", doctor={"id": "DOC-003", "display": _DOCTOR_NAMES["DOC-003"]})
            elif service["id"] == "SERVICE-ECHO-001":
                doctor_id = "DOC-001" if start_time.hour < 12 else "DOC-002"
                item.update(doctor_id=doctor_id, doctor={"id": doctor_id, "display": _DOCTOR_NAMES[doctor_id]})
            result.append(item)
    return result


def seed_appointments(reference_date: date, patient_id: str) -> list[dict]:
    """Build three stable synthetic history records for one configured patient.

    A booked ultrasound conflicts with 15:00 cardiology but ends before 15:30.
    A cancelled 15:30 registration demonstrates that cancellations do not block
    availability or conflict checks.  The returned history is not persisted here.
    """
    if not isinstance(patient_id, str) or not patient_id.strip():
        raise ValueError("patient_id must be a non-empty string")
    target_day = next_tuesday(reference_date)
    rehab_day = reference_date + timedelta(days=1)
    while rehab_day.weekday() >= 5:
        rehab_day += timedelta(days=1)
    namespace = sha256(patient_id.encode("utf-8")).hexdigest()[:12].upper()
    departments_by_id = {item["id"]: item for item in departments()}
    services_by_id = {item["id"]: item for item in appointment_services()}

    selections = (
        ("IMAGING", target_day, "booked", next(slot for slot in appointment_slots_for_date(target_day) if slot["service_id"] == "SERVICE-US-001" and slot["start"][11:16] == "14:45")),
        ("REHAB", rehab_day, "confirmed", next(slot for slot in appointment_slots_for_date(rehab_day) if slot["service_id"] == "SERVICE-PT-001" and slot["start"][11:16] == "10:00")),
        ("CANCELLED-CARDIO", target_day, "cancelled", next(slot for slot in registration_slots_for_date(target_day) if slot["start"][11:16] == "15:30")),
    )
    result = []
    for label, day, status, slot in selections:
        department = departments_by_id[slot["department_id"]]
        item = {
            "resourceType": "Appointment",
            "id": f"APT-DEMO-SEED-{namespace}-{label}-{day:%Y%m%d}",
            "status": status,
            "appointment_type": slot["slot_type"],
            "patient_id": patient_id,
            "patient": {"id": patient_id, "display": _PATIENT_DISPLAY},
            "department": {"id": department["id"], "display": department["name"]},
            "doctor": deepcopy(slot.get("doctor")),
            "location": deepcopy(slot["location"]),
            "start": slot["start"],
            "end": slot["end"],
            "slot_id": slot["id"],
            "booking_source": "ponte_mock_seed",
            "instructions": deepcopy(slot["instructions"]),
            "synthetic": True,
        }
        if slot.get("service_id"):
            service = services_by_id[slot["service_id"]]
            item["service"] = {"id": service["id"], "display": service["name"]}
        if status == "cancelled":
            item["cancellation_reason"] = "模擬病人已取消；不應佔用時段或視作撞期。"
        result.append(item)
    return result
