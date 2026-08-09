"""Pure-data contracts for the optional synthetic live medical profile."""

from copy import deepcopy
from datetime import date, datetime, timedelta
import unittest

from mock_backends.medical.demo_profile import (
    PROFILE_NAME,
    appointment_slots_for_date,
    build_demo_catalogue,
    registration_slots_for_date,
    seed_appointments,
)
from mock_backends.medical.fixtures import (
    APPOINTMENT_SERVICES,
    DEPARTMENTS,
    DOCTORS,
    LOCATION_DISPLAYS,
    cardiology_demo_slots,
)


class LiveDemoProfileTests(unittest.TestCase):
    reference = date(2026, 10, 14)
    target = date(2026, 10, 20)

    def test_catalogue_keeps_existing_identifiers_and_valid_references(self):
        catalogue = build_demo_catalogue(self.reference)
        self.assertEqual(PROFILE_NAME, "live-demo-v2")
        self.assertEqual(catalogue["reference_date"], "2026-10-14")
        self.assertEqual(catalogue["timezone"], "Asia/Macau")
        departments = {item["id"]: item for item in catalogue["departments"]}
        self.assertEqual(set(departments), {item["id"] for item in DEPARTMENTS})
        self.assertEqual({item["id"] for item in catalogue["doctors"]}, {item["id"] for item in DOCTORS})
        self.assertEqual({item["id"] for item in catalogue["appointment_services"]}, {item["id"] for item in APPOINTMENT_SERVICES})
        for item in catalogue["departments"] + catalogue["doctors"] + catalogue["appointment_services"]:
            self.assertTrue(item["synthetic"])
            self.assertIn(item["location"]["id"], LOCATION_DISPLAYS)
            self.assertEqual(item["location"]["display"], LOCATION_DISPLAYS[item["location"]["id"]])
            if "department_id" in item:
                self.assertIn(item["department_id"], departments)
        for service in catalogue["appointment_services"]:
            self.assertTrue(service["requires_referral"])
            self.assertTrue(service["instructions"])
            self.assertIn("模擬", service["description"])

    def test_slot_dates_ids_durations_and_references_are_consistent(self):
        catalogue = build_demo_catalogue(self.reference)
        departments = {item["id"]: item for item in catalogue["departments"]}
        doctors = {item["id"]: item for item in catalogue["doctors"]}
        services = {item["id"]: item for item in catalogue["appointment_services"]}
        slots = registration_slots_for_date(self.target) + appointment_slots_for_date(self.target)
        self.assertEqual(len({item["id"] for item in slots}), len(slots))
        for slot in slots:
            start, end = (datetime.fromisoformat(slot[key]) for key in ("start", "end"))
            self.assertEqual(start.date(), self.target)
            self.assertEqual(end.date(), self.target)
            self.assertEqual(start.utcoffset(), timedelta(hours=8))
            self.assertEqual(end.utcoffset(), timedelta(hours=8))
            self.assertIn("20261020", slot["id"])
            self.assertTrue(slot["id"].startswith("SLOT-LIVE-V2-"))
            self.assertIn(slot["department_id"], departments)
            self.assertEqual(slot["location_id"], departments[slot["department_id"]]["location_id"])
            self.assertLessEqual(slot["remaining"], slot["capacity"])
            self.assertEqual(slot["status"], "free" if slot["remaining"] else "busy")
            if "doctor_id" in slot:
                self.assertEqual(doctors[slot["doctor_id"]]["department_id"], slot["department_id"])
                self.assertEqual(slot["doctor"]["display"], doctors[slot["doctor_id"]]["name"])
            expected_duration = 15
            if "service_id" in slot:
                service = services[slot["service_id"]]
                expected_duration = service["duration_minutes"]
                self.assertEqual(slot["requires_referral"], service["requires_referral"])
                self.assertEqual(slot["slot_type"], service["type"])
            self.assertEqual(end - start, timedelta(minutes=expected_duration))

    def test_schedule_covers_boundary_choices_and_full_slot(self):
        registration = registration_slots_for_date(self.target)
        self.assertEqual([slot["start"][11:16] for slot in registration if slot["remaining"]], ["09:00", "10:30", "14:00", "15:00", "15:30", "16:00"])
        full = [slot for slot in registration if slot["remaining"] == 0]
        self.assertEqual([slot["start"][11:16] for slot in full], ["15:15"])
        appointments = appointment_slots_for_date(self.target)
        self.assertEqual(len(appointments), 6)
        self.assertTrue(all(sum(slot["service_id"] == service["id"] for slot in appointments) == 2 for service in APPOINTMENT_SERVICES))
        for day in (date(2026, 10, 17), date(2026, 10, 18)):
            self.assertEqual(registration_slots_for_date(day), [])
            self.assertEqual(appointment_slots_for_date(day), [])

    def test_inventory_is_date_stable_and_never_rebases_ids(self):
        first = registration_slots_for_date(self.target) + appointment_slots_for_date(self.target)
        self.assertEqual(first, registration_slots_for_date(self.target) + appointment_slots_for_date(self.target))
        second = registration_slots_for_date(self.target + timedelta(days=1)) + appointment_slots_for_date(self.target + timedelta(days=1))
        self.assertTrue({item["id"] for item in first}.isdisjoint(item["id"] for item in second))
        # Building a later catalogue must not move any previously issued slot.
        build_demo_catalogue(self.target + timedelta(days=1))
        self.assertEqual(first, registration_slots_for_date(self.target) + appointment_slots_for_date(self.target))

    def test_history_has_real_conflict_clear_choice_and_cancelled_choice(self):
        history = seed_appointments(self.reference, "PAT-DEMO-001")
        self.assertEqual(len(history), 3)
        self.assertEqual({item["status"] for item in history}, {"booked", "confirmed", "cancelled"})
        self.assertTrue(all(item["id"].startswith("APT-DEMO-SEED-") for item in history))
        self.assertTrue(all(item["patient_id"] == "PAT-DEMO-001" and item["synthetic"] for item in history))
        ultrasound = next(item for item in history if item["appointment_type"] == "examination")
        self.assertEqual(ultrasound["start"], "2026-10-20T14:45:00+08:00")
        self.assertEqual(ultrasound["end"], "2026-10-20T15:15:00+08:00")
        cancelled = next(item for item in history if item["status"] == "cancelled")
        self.assertEqual(cancelled["start"], "2026-10-20T15:30:00+08:00")
        self.assertEqual(cancelled["appointment_type"], "outpatient_registration")
        active_intervals = [
            (datetime.fromisoformat(item["start"]), datetime.fromisoformat(item["end"]))
            for item in history if item["status"] in {"booked", "confirmed"}
        ]
        for clock_time, expected_overlap in (("15:00", True), ("15:30", False)):
            slot = next(item for item in registration_slots_for_date(self.target) if item["start"][11:16] == clock_time)
            start, end = (datetime.fromisoformat(slot[key]) for key in ("start", "end"))
            self.assertEqual(any(start < other_end and other_start < end for other_start, other_end in active_intervals), expected_overlap)
        all_slots = {}
        for day in {date.fromisoformat(item["start"][:10]) for item in history}:
            all_slots.update({slot["id"]: slot for slot in registration_slots_for_date(day) + appointment_slots_for_date(day)})
        for item in history:
            slot = all_slots[item["slot_id"]]
            self.assertEqual((item["start"], item["end"]), (slot["start"], slot["end"]))
            self.assertEqual(item["location"], slot["location"])
            self.assertEqual(item["department"]["id"], slot["department_id"])
        self.assertEqual(history, seed_appointments(self.reference, "PAT-DEMO-001"))
        self.assertTrue({item["id"] for item in history}.isdisjoint(item["id"] for item in seed_appointments(self.reference, "PAT-OTHER")))

    def test_seed_dates_handle_weekends_and_strict_next_tuesday(self):
        friday = seed_appointments(date(2026, 10, 16), "PAT-DEMO-001")
        rehab = next(item for item in friday if item["appointment_type"] == "treatment")
        self.assertEqual(rehab["start"][:10], "2026-10-19")
        tuesday = seed_appointments(date(2026, 10, 20), "PAT-DEMO-001")
        imaging = next(item for item in tuesday if item["appointment_type"] == "examination")
        self.assertEqual(imaging["start"][:10], "2026-10-27")
        for patient_id in ("", "   ", None):
            with self.subTest(patient_id=patient_id), self.assertRaises(ValueError):
                seed_appointments(self.reference, patient_id)

    def test_mutation_isolation_preserves_legacy_and_subsequent_calls(self):
        legacy = deepcopy((DEPARTMENTS, DOCTORS, APPOINTMENT_SERVICES, cardiology_demo_slots(self.target)))
        catalogue = build_demo_catalogue(self.reference)
        catalogue["departments"][0]["location"]["display"] = "changed"
        catalogue["doctors"][0]["name"] = "changed"
        catalogue["appointment_services"][0]["instructions"].clear()
        slots = registration_slots_for_date(self.target)
        slots[0]["location"]["display"] = "changed"
        slots[0]["instructions"].clear()
        history = seed_appointments(self.reference, "PAT-DEMO-001")
        history[0]["patient"]["display"] = "changed"
        history[0]["instructions"].clear()
        fresh_catalogue = build_demo_catalogue(self.reference)
        self.assertNotEqual(fresh_catalogue["departments"][0]["location"]["display"], "changed")
        self.assertNotEqual(fresh_catalogue["doctors"][0]["name"], "changed")
        self.assertTrue(fresh_catalogue["appointment_services"][0]["instructions"])
        self.assertTrue(registration_slots_for_date(self.target)[0]["instructions"])
        self.assertTrue(seed_appointments(self.reference, "PAT-DEMO-001")[0]["instructions"])
        self.assertEqual(legacy, (DEPARTMENTS, DOCTORS, APPOINTMENT_SERVICES, cardiology_demo_slots(self.target)))


if __name__ == "__main__":
    unittest.main()
