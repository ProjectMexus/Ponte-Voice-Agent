"""FHIR-inspired read-only catalogues for the medical demo."""

from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta


LOCATION_DISPLAYS = {
    "LOC-MAIN-OPD": "第一門診",
    "LOC-IMAGING-CENTER": "影像中心",
    "LOC-REHAB-01": "復康治療室",
}


DEPARTMENTS = [
    {"resourceType": "Organization", "id": "DEPT-CARDIO", "name": "心臟科", "name_en": "Cardiology", "location_id": "LOC-MAIN-OPD", "active": True},
    {"resourceType": "Organization", "id": "DEPT-IMAGING", "name": "影像科", "name_en": "Imaging", "location_id": "LOC-IMAGING-CENTER", "active": True},
    {"resourceType": "Organization", "id": "DEPT-REHAB", "name": "復康治療科", "name_en": "Rehabilitation", "location_id": "LOC-REHAB-01", "active": True},
]

DOCTORS = [
    {"resourceType": "Practitioner", "id": "DOC-001", "name": "陳醫生", "name_en": "Dr. Chan", "department_id": "DEPT-CARDIO", "specialty": "心臟科", "active": True},
    {"resourceType": "Practitioner", "id": "DOC-002", "name": "李醫生", "name_en": "Dr. Lee", "department_id": "DEPT-CARDIO", "specialty": "心臟科", "active": True},
    {"resourceType": "Practitioner", "id": "DOC-003", "name": "周醫生", "name_en": "Dr. Chow", "department_id": "DEPT-REHAB", "specialty": "復康治療", "active": True},
]

REGISTRATION_SLOTS = [
    {"resourceType": "Slot", "id": "SLOT-REG-20260812-CARDIO-1030", "status": "free", "slot_type": "outpatient_registration", "department_id": "DEPT-CARDIO", "doctor_id": "DOC-001", "location_id": "LOC-MAIN-OPD", "start": "2026-08-12T10:30:00+08:00", "end": "2026-08-12T10:45:00+08:00", "capacity": 10, "remaining": 6, "session": "morning"},
    {"resourceType": "Slot", "id": "SLOT-REG-20260812-CARDIO-1100", "status": "free", "slot_type": "outpatient_registration", "department_id": "DEPT-CARDIO", "doctor_id": "DOC-001", "location_id": "LOC-MAIN-OPD", "start": "2026-08-12T11:00:00+08:00", "end": "2026-08-12T11:15:00+08:00", "capacity": 10, "remaining": 3, "session": "morning"},
    {"resourceType": "Slot", "id": "SLOT-REG-20260812-CARDIO-1400", "status": "free", "slot_type": "outpatient_registration", "department_id": "DEPT-CARDIO", "doctor_id": "DOC-002", "location_id": "LOC-MAIN-OPD", "start": "2026-08-12T14:00:00+08:00", "end": "2026-08-12T14:15:00+08:00", "capacity": 8, "remaining": 8, "session": "afternoon"},
    {"resourceType": "Slot", "id": "SLOT-REG-20260812-CARDIO-FULL", "status": "busy", "slot_type": "outpatient_registration", "department_id": "DEPT-CARDIO", "doctor_id": "DOC-001", "location_id": "LOC-MAIN-OPD", "start": "2026-08-12T15:00:00+08:00", "end": "2026-08-12T15:15:00+08:00", "capacity": 1, "remaining": 0, "session": "afternoon"},
]

APPOINTMENT_SERVICES = [
    {"resourceType": "HealthcareService", "id": "SERVICE-US-001", "name": "腹部超聲波檢查", "name_en": "Abdominal Ultrasound", "type": "examination", "department_id": "DEPT-IMAGING", "location_id": "LOC-IMAGING-CENTER", "duration_minutes": 30, "requires_referral": True, "active": True},
    {"resourceType": "HealthcareService", "id": "SERVICE-PT-001", "name": "物理治療", "name_en": "Physical Therapy", "type": "treatment", "department_id": "DEPT-REHAB", "location_id": "LOC-REHAB-01", "duration_minutes": 45, "requires_referral": True, "active": True},
    {"resourceType": "HealthcareService", "id": "SERVICE-ECHO-001", "name": "心臟超聲波檢查", "name_en": "Cardiac Ultrasound", "type": "examination", "department_id": "DEPT-CARDIO", "location_id": "LOC-MAIN-OPD", "duration_minutes": 30, "requires_referral": True, "active": True},
]

APPOINTMENT_SLOTS = [
    {"resourceType": "Slot", "id": "SLOT-US-20260812-1400", "status": "free", "slot_type": "examination", "service_id": "SERVICE-US-001", "department_id": "DEPT-IMAGING", "location_id": "LOC-IMAGING-CENTER", "start": "2026-08-12T14:00:00+08:00", "end": "2026-08-12T14:30:00+08:00", "capacity": 1, "remaining": 1},
    {"resourceType": "Slot", "id": "SLOT-PT-20260813-1000", "status": "free", "slot_type": "treatment", "service_id": "SERVICE-PT-001", "department_id": "DEPT-REHAB", "location_id": "LOC-REHAB-01", "start": "2026-08-13T10:00:00+08:00", "end": "2026-08-13T10:45:00+08:00", "capacity": 2, "remaining": 2},
    {"resourceType": "Slot", "id": "SLOT-US-20260813-0930", "status": "free", "slot_type": "examination", "service_id": "SERVICE-US-001", "department_id": "DEPT-IMAGING", "location_id": "LOC-IMAGING-CENTER", "start": "2026-08-13T09:30:00+08:00", "end": "2026-08-13T10:00:00+08:00", "capacity": 1, "remaining": 1},
    {"resourceType": "Slot", "id": "SLOT-US-20260814-1500", "status": "free", "slot_type": "examination", "service_id": "SERVICE-US-001", "department_id": "DEPT-IMAGING", "location_id": "LOC-IMAGING-CENTER", "start": "2026-08-14T15:00:00+08:00", "end": "2026-08-14T15:30:00+08:00", "capacity": 1, "remaining": 1},
    {"resourceType": "Slot", "id": "SLOT-PT-20260812-1000", "status": "free", "slot_type": "treatment", "service_id": "SERVICE-PT-001", "department_id": "DEPT-REHAB", "location_id": "LOC-REHAB-01", "start": "2026-08-12T10:00:00+08:00", "end": "2026-08-12T10:45:00+08:00", "capacity": 2, "remaining": 2},
    {"resourceType": "Slot", "id": "SLOT-PT-20260814-1400", "status": "free", "slot_type": "treatment", "service_id": "SERVICE-PT-001", "department_id": "DEPT-REHAB", "location_id": "LOC-REHAB-01", "start": "2026-08-14T14:00:00+08:00", "end": "2026-08-14T14:45:00+08:00", "capacity": 2, "remaining": 2},
    {"resourceType": "Slot", "id": "SLOT-ECHO-20260812-0900", "status": "free", "slot_type": "examination", "service_id": "SERVICE-ECHO-001", "department_id": "DEPT-CARDIO", "location_id": "LOC-MAIN-OPD", "start": "2026-08-12T09:00:00+08:00", "end": "2026-08-12T09:30:00+08:00", "capacity": 1, "remaining": 1},
    {"resourceType": "Slot", "id": "SLOT-ECHO-20260813-1500", "status": "free", "slot_type": "examination", "service_id": "SERVICE-ECHO-001", "department_id": "DEPT-CARDIO", "location_id": "LOC-MAIN-OPD", "start": "2026-08-13T15:00:00+08:00", "end": "2026-08-13T15:30:00+08:00", "capacity": 1, "remaining": 1},
    {"resourceType": "Slot", "id": "SLOT-ECHO-20260814-1100", "status": "free", "slot_type": "examination", "service_id": "SERVICE-ECHO-001", "department_id": "DEPT-CARDIO", "location_id": "LOC-MAIN-OPD", "start": "2026-08-14T11:00:00+08:00", "end": "2026-08-14T11:30:00+08:00", "capacity": 1, "remaining": 1},
]


def departments() -> list[dict]:
    return deepcopy(DEPARTMENTS)


def doctors() -> list[dict]:
    return deepcopy(DOCTORS)


def next_tuesday(reference_date: date) -> date:
    """Resolve 'next Tuesday' strictly after the service's reference day."""
    return reference_date + timedelta(days=(1 - reference_date.weekday()) % 7 or 7)


def cardiology_demo_slots(selected_date: date) -> list[dict]:
    """Isolated inventory: dated IDs never rebase or replace legacy bookings."""
    result = []
    for hour, minute in ((14, 0), (15, 30)):
        start = f"{selected_date.isoformat()}T{hour:02d}:{minute:02d}:00+08:00"
        end = f"{selected_date.isoformat()}T{hour:02d}:{minute + 15:02d}:00+08:00"
        result.append({
            "resourceType": "Slot",
            "id": f"SLOT-DEMO-REG-{selected_date:%Y%m%d}-CARDIO-{hour:02d}{minute:02d}",
            "status": "free",
            "slot_type": "outpatient_registration",
            "department_id": "DEPT-CARDIO",
            "doctor_id": "DOC-002",
            "location_id": "LOC-MAIN-OPD",
            "location": {"id": "LOC-MAIN-OPD", "display": LOCATION_DISPLAYS["LOC-MAIN-OPD"]},
            "start": start,
            "end": end,
            "capacity": 1,
            "remaining": 1,
            "session": "afternoon",
        })
    return result


def _dated_slots(templates: list[dict], now: datetime | None) -> list[dict]:
    if now is None:
        return deepcopy(templates)
    # Offer today's unelapsed times and the next three days. Date-bearing IDs
    # stay stable when the window rolls, so saved bookings retain capacity.
    result: dict[str, dict] = {}
    for offset in range(4):
        slot_date = now.date() + timedelta(days=offset)
        for template in templates:
            item = deepcopy(template)
            original_date = datetime.fromisoformat(item["start"]).date()
            shift = slot_date - original_date
            item["id"] = item["id"].replace(original_date.strftime("%Y%m%d"), slot_date.strftime("%Y%m%d"))
            for field in ("start", "end"):
                item[field] = (datetime.fromisoformat(item[field]) + shift).isoformat()
            if datetime.fromisoformat(item["start"]) <= now:
                continue
            result.setdefault(item["id"], item)
    return list(result.values())

def registration_slots(demo_date: date | None = None, *, now: datetime | None = None) -> list[dict]:
    if isinstance(demo_date, datetime):
        now, demo_date = demo_date, None
    slots = _dated_slots(REGISTRATION_SLOTS, now)
    if demo_date is not None:
        slots.extend(cardiology_demo_slots(demo_date))
    return slots


def _with_locations(records: list[dict]) -> list[dict]:
    result = deepcopy(records)
    for item in result:
        location_id = item["location_id"]
        item["location"] = {"id": location_id, "display": LOCATION_DISPLAYS[location_id]}
    return result


def appointment_services() -> list[dict]:
    return _with_locations(APPOINTMENT_SERVICES)


def appointment_slots(reference_date: date | None = None, *, now: datetime | None = None) -> list[dict]:
    if isinstance(reference_date, datetime):
        now, reference_date = reference_date, None
    slots = _with_locations(_dated_slots(APPOINTMENT_SLOTS, now))
    if reference_date is not None:
        shift = reference_date - date(2026, 8, 12)
        for slot in slots:
            for field in ("start", "end"):
                slot[field] = (datetime.fromisoformat(slot[field]) + shift).isoformat()
    return slots
