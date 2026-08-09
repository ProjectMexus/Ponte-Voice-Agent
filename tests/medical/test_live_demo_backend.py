"""Persistent composition and capacity checks for the richer opt-in dataset."""

from datetime import datetime
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from mock_backends.core.clock import FixedClock, MACAU_TZ
from mock_backends.core.http import BackendRequest
from mock_backends.core.persistence import JsonLinesTextRepository
from mock_backends.medical.demo_profile import PROFILE_NAME, seed_appointments
from mock_backends.server import create_application
from scripts.run_stack import build_commands


class LiveMedicalBackendTests(unittest.TestCase):
    patient = "PAT-LIVE-TEST"

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.root = Path(self.tempdir.name)
        self.clock = FixedClock(datetime(2026, 10, 13, 9, tzinfo=MACAU_TZ))
        self.app = self.application()
        self.records = JsonLinesTextRepository(self.root / "medical" / "appointments.txt")

    def application(self, clock=None, **kwargs):
        return create_application(self.root, clock=clock or self.clock,
                                  medical_data_profile=PROFILE_NAME, patient_id=self.patient, **kwargs)

    def request(self, method, suffix, *, body=None, query=None, patient=None, key="LIVE-TEST", app=None):
        return (app or self.app).dispatch(BackendRequest(
            method=method, path="/mock/medical/v1" + suffix,
            headers={"X-Patient-Id": patient or self.patient, "Idempotency-Key": key,
                     "Authorization": "Bearer mock-user-token"},
            query={k: [v] for k, v in (query or {}).items()}, body=body, request_id="REQ-LIVE-TEST",
        ))

    def search(self, day="2026-10-20", session="afternoon", **kwargs):
        return self.request("GET", "/registration-slots", query={
            "department_id": "DEPT-CARDIO", "date": day, "session": session,
        }, **kwargs)

    def booking(self, time="1530", day="20261020", **kwargs):
        return self.request("POST", "/registrations", body={
            "patient_id": self.patient, "department_id": "DEPT-CARDIO", "consent": True,
            "slot_id": f"SLOT-LIVE-V2-REG-{day}-CARDIO-{time}",
        }, **kwargs)

    def test_live_history_and_inventory_are_consistent_and_patient_scoped(self):
        history = self.request("GET", "/appointments")
        self.assertEqual(history.status, 200)
        self.assertEqual(len(history.body["data"]), 3)
        self.assertTrue(all(item["synthetic"] for item in history.body["data"]))
        self.assertFalse(history.body["meta"]["has_next"])
        self.assertEqual(self.request("GET", "/appointments", patient="PAT-OTHER").body["data"], [])
        slots = self.search()
        self.assertEqual(slots.body["meta"]["data_profile"], PROFILE_NAME)
        self.assertEqual([s["start"][11:16] for s in slots.body["data"]], ["14:00", "15:00", "15:30", "16:00"])
        # The seed's booked ultrasound consumes its exact inventory, not all same-day appointments.
        imaging = self.request("GET", "/appointment-slots", query={
            "service_id": "SERVICE-US-001", "date_from": "2026-10-20", "date_to": "2026-10-20",
        })
        self.assertEqual([s["start"][11:16] for s in imaging.body["data"]], ["09:30"])

    def test_cancelled_history_does_not_block_booking_or_idempotent_replay(self):
        first = self.booking()
        repeated = self.booking()
        self.assertEqual(first.status, 201)
        self.assertEqual(first.body, repeated.body)
        self.assertEqual(len(self.records.list()), 4)
        appointment = first.body["data"]
        self.assertTrue(appointment["synthetic"])
        self.assertIn("模擬", appointment["patient"]["display"])
        self.assertEqual(appointment["doctor"], {"id": "DOC-002", "display": "李醫生（模擬）"})
        self.assertEqual(appointment["location"]["display"], "第一門診")
        self.assertTrue(any("模擬" in text for text in appointment["instructions"]))
        self.assertNotIn("15:30", [s["start"][11:16] for s in self.search().body["data"]])
        self.assertEqual(self.booking(key="OTHER-KEY").status, 409)
        self.assertEqual(len(self.records.list()), 4)

    def test_full_slot_rejected_without_new_appointment(self):
        full = self.booking(time="1515")
        self.assertEqual(full.status, 409)
        self.assertEqual(full.body["error"]["code"], "SLOT_NOT_AVAILABLE")
        self.assertEqual(len(self.records.list()), 3)

    def test_current_day_past_times_and_window_boundaries(self):
        morning = self.search(day="2026-10-13", session="morning")
        self.assertEqual([s["start"][11:16] for s in morning.body["data"]], ["10:30"])
        expired = self.booking(time="0900", day="20261013")
        self.assertEqual(expired.status, 409)
        self.assertEqual(expired.body["error"]["code"], "SLOT_EXPIRED")
        self.assertTrue(self.search(day="2026-10-27").body["data"])
        self.assertEqual(self.search(day="2026-10-28").status, 422)
        self.assertEqual(self.search(day="2026-10-17").body["data"], [])
        self.assertEqual(self.booking(day="20261028").status, 404)

    def test_restart_preserves_saved_bytes_dates_and_consumed_capacity(self):
        created = self.booking().body["data"]
        path = self.root / "medical" / "appointments.txt"
        saved = path.read_bytes()
        restart = self.application(FixedClock(datetime(2026, 10, 14, 9, tzinfo=MACAU_TZ)))
        self.assertEqual(path.read_bytes(), saved)
        self.assertNotIn("15:30", [s["start"][11:16] for s in self.search(app=restart).body["data"]])
        later = self.application(FixedClock(datetime(2026, 10, 21, 9, tzinfo=MACAU_TZ)))
        self.assertTrue(self.search(day="2026-10-27", app=later).body["data"])
        detail = self.request("GET", "/appointments/" + created["id"], app=later)
        self.assertEqual(detail.body["data"]["start"], "2026-10-20T15:30:00+08:00")
        self.assertEqual(path.read_bytes(), saved)

    def test_partial_seed_recovery_does_not_overwrite_existing_record(self):
        other_root = self.root / "partial"
        seeds = seed_appointments(self.clock.now().date(), self.patient)
        with patch("mock_backends.server.seed_appointments", return_value=seeds[:1]):
            create_application(other_root, self.clock, medical_data_profile=PROFILE_NAME, patient_id=self.patient)
        repository = JsonLinesTextRepository(other_root / "medical" / "appointments.txt")
        original = repository.get(seeds[0]["id"])
        original["status"] = "cancelled"
        repository.replace(original["id"], original)
        create_application(other_root, self.clock, medical_data_profile=PROFILE_NAME, patient_id=self.patient)
        self.assertEqual(len(repository.list()), 3)
        self.assertEqual(repository.get(original["id"]), original)

    def test_profile_and_patient_mismatch_rejected_without_changing_records(self):
        path = self.root / "medical" / "appointments.txt"
        saved = path.read_bytes()
        with self.assertRaises(ValueError):
            create_application(self.root, self.clock, medical_data_profile=PROFILE_NAME, patient_id="PAT-OTHER")
        with self.assertRaises(ValueError):
            create_application(self.root, self.clock)
        self.assertEqual(path.read_bytes(), saved)

    def test_existing_legacy_directory_is_not_migrated_implicitly(self):
        other_root = self.root / "legacy"
        path = other_root / "medical" / "appointments.txt"
        repository = JsonLinesTextRepository(path)
        repository.insert({"id": "APT-LEGACY", "patient_id": self.patient, "status": "booked"})
        saved = path.read_bytes()
        with self.assertRaises(ValueError):
            create_application(other_root, self.clock, medical_data_profile=PROFILE_NAME, patient_id=self.patient)
        self.assertEqual(path.read_bytes(), saved)
        self.assertFalse((other_root / "medical" / "demo_profile.txt").exists())

    def test_api_defaults_remain_legacy_even_with_deployment_environment(self):
        with patch.dict("os.environ", {"PONTE_MEDICAL_DATA_PROFILE": PROFILE_NAME}):
            legacy = create_application(self.root / "legacy-default", self.clock)
        self.assertEqual(len(self.search(app=legacy).body["data"]), 2)
        self.assertEqual(self.request("GET", "/appointments", app=legacy).body["data"], [])

    def test_exam_receipt_retains_doctor_and_synthetic_details(self):
        created = self.request("POST", "/appointments", body={
            "patient_id": self.patient, "service_id": "SERVICE-ECHO-001", "consent": True,
            "slot_id": "SLOT-LIVE-V2-APT-20261020-ECHO-1600", "referring_appointment_id": "APT-DEMO-REF",
        })
        self.assertEqual(created.status, 201)
        self.assertTrue(created.body["data"]["synthetic"])
        self.assertEqual(created.body["data"]["doctor"]["id"], "DOC-002")
        self.assertTrue(any("模擬" in item for item in created.body["data"]["instructions"]))

    def test_stack_command_explicitly_selects_v2(self):
        commands = build_commands("python", backend_port=8080, middleware_port=8090,
                                  frontend_port=5173, data_dir=self.root, medical_data_profile=PROFILE_NAME)
        self.assertEqual(commands.backend[-2:], ["--medical-data-profile", PROFILE_NAME])


if __name__ == "__main__":
    unittest.main()
