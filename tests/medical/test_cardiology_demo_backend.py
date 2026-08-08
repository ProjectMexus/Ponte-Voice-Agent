"""Reproducible cardiology inventory and process-local write serialization."""

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from threading import Barrier, Event
from unittest.mock import patch

from mock_backends.core.clock import FixedClock, MACAU_TZ
from mock_backends.core.http import BackendRequest
from mock_backends.core.idempotency import RepositoryIdempotencyStore
from mock_backends.core.ids import SequentialIdGenerator
from mock_backends.core.persistence import JsonLinesTextRepository, MemoryRepository
from mock_backends.medical.backend import MedicalBackend
from mock_backends.medical.fixtures import next_tuesday
from mock_backends.medical.service import MedicalService
from mock_backends.server import create_application


class CardiologyDemoBackendTests(unittest.TestCase):
    def setUp(self):
        self.clock = FixedClock(datetime(2026, 10, 13, 9, tzinfo=MACAU_TZ))
        self.appointments = MemoryRepository()
        self.tasks = MemoryRepository()
        self.replays = MemoryRepository()
        self.service = MedicalService(
            clock=self.clock,
            ids=SequentialIdGenerator(),
            appointment_repository=self.appointments,
            task_repository=self.tasks,
            idempotency=RepositoryIdempotencyStore(self.replays),
        )
        self.backend = MedicalBackend(self.service)

    def request(self, method, suffix, *, patient="P-CARDIO-DEMO", key="CARDIO-P2", body=None, query=None):
        return BackendRequest(
            method=method,
            path=f"/mock/medical/v1{suffix}",
            headers={"Authorization": "Bearer mock-user-token", "X-Patient-Id": patient, "Idempotency-Key": key},
            body=body,
            query=query or {},
            request_id="REQ-CARDIO-DEMO",
        )

    def search_request(self):
        return self.request("GET", "/registration-slots", query={
            "department_id": ["DEPT-CARDIO"], "date": ["2026-10-20"], "session": ["afternoon"],
        })

    def booking(self, *, patient="P-CARDIO-DEMO", key="CARDIO-P2", time="1530"):
        return self.request("POST", "/registrations", patient=patient, key=key, body={
            "patient_id": patient,
            "department_id": "DEPT-CARDIO",
            "doctor_id": "DOC-002",
            "slot_id": f"SLOT-DEMO-REG-20261020-CARDIO-{time}",
            "consent": True,
        })

    def test_service_clock_resolves_isolated_next_tuesday_inventory(self):
        self.assertEqual(next_tuesday(date(2026, 10, 13)), date(2026, 10, 20))
        self.assertEqual(next_tuesday(date(2026, 10, 14)), date(2026, 10, 20))
        response = self.backend.handle(self.search_request())
        self.assertEqual(response.status, 200)
        slots = response.body["data"]
        self.assertEqual([item["start"] for item in slots], [
            "2026-10-20T14:00:00+08:00", "2026-10-20T15:30:00+08:00",
        ])
        self.assertEqual([item["remaining"] for item in slots], [1, 1])
        self.assertTrue(all(item["location"]["display"] == "第一門診" for item in slots))
        self.assertEqual(self.appointments.list(), [])

    def test_fixture_date_can_be_injected_without_changing_legacy_slots(self):
        self.service = MedicalService(
            clock=self.clock,
            ids=SequentialIdGenerator(),
            appointment_repository=self.appointments,
            task_repository=self.tasks,
            idempotency=RepositoryIdempotencyStore(self.replays),
            registration_slot_reference_date=date(2026, 10, 21),
        )
        self.backend = MedicalBackend(self.service)
        self.assertEqual(self.backend.handle(self.search_request()).body["data"], [])
        self.assertEqual(
            self.service._registration_slot("SLOT-REG-20260812-CARDIO-1030")["start"],
            "2026-08-12T10:30:00+08:00",
        )

    def test_live_catalogue_preserves_existing_booking_bytes_and_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            appointments_file = root / "medical" / "appointments.txt"
            repository = JsonLinesTextRepository(appointments_file)
            repository.insert({
                "id": "APT-LEGACY", "patient_id": "P-LEGACY", "status": "booked",
                "slot_id": "SLOT-REG-20260812-CARDIO-1030", "start": "2026-08-12T10:30:00+08:00",
            })
            saved_bytes = appointments_file.read_bytes()
            with patch("mock_backends.server.AsiaMacauClock", return_value=self.clock):
                application = create_application(root)
            slots = application.dispatch(self.search_request()).body["data"]
            self.assertEqual(len(slots), 2)
            self.assertEqual(appointments_file.read_bytes(), saved_bytes)
            booked = application.dispatch(self.booking())
            self.assertEqual(booked.status, 201)
            self.assertEqual(repository.get("APT-LEGACY")["start"], "2026-08-12T10:30:00+08:00")
            restarted = create_application(root, clock=self.clock)
            remaining = restarted.dispatch(self.search_request()).body["data"]
            self.assertEqual([item["start"] for item in remaining], ["2026-10-20T14:00:00+08:00"])

    def test_registration_result_contains_backend_facts_and_replays_without_capacity(self):
        first = self.backend.handle(self.booking())
        replay = self.backend.handle(self.booking())
        self.assertEqual(first.status, 201)
        self.assertEqual(first.body, replay.body)
        appointment = first.body["data"]
        self.assertEqual(appointment["status"], "booked")
        self.assertEqual(appointment["patient_id"], "P-CARDIO-DEMO")
        self.assertEqual(appointment["department"]["id"], "DEPT-CARDIO")
        self.assertEqual(appointment["slot_id"], "SLOT-DEMO-REG-20261020-CARDIO-1530")
        self.assertEqual(appointment["start"], "2026-10-20T15:30:00+08:00")
        self.assertEqual(first.body["task"]["id"], appointment["task_id"])
        self.assertEqual(first.body["task"]["status"], "completed")
        self.assertEqual(first.body["task"]["appointment_id"], appointment["id"])
        self.assertRegex(first.body["receipt"]["reference"], r"^MED-REG-\d+$")
        self.assertEqual(len(self.appointments.list()), 1)
        self.assertEqual(len(self.tasks.list()), 1)
        self.assertEqual(len(self.replays.list()), 1)

    def test_same_key_with_changed_payload_is_rejected_without_another_booking(self):
        self.assertEqual(self.backend.handle(self.booking()).status, 201)
        rejected = self.backend.handle(self.booking(time="1400"))
        self.assertEqual(rejected.status, 409)
        self.assertEqual(rejected.body["error"]["code"], "IDEMPOTENCY_KEY_REUSED")
        self.assertEqual(len(self.appointments.list()), 1)

    def test_concurrent_duplicate_waits_for_replay_save_and_returns_same_result(self):
        saving = Event()
        release = Event()
        second_started = Event()
        second_returned = Event()
        original_remember = self.service.idempotency.remember

        def paused_remember(*args):
            if not saving.is_set():
                saving.set()
                self.assertTrue(release.wait(3), "test did not release replay save")
            return original_remember(*args)

        def duplicate():
            second_started.set()
            result = self.backend.handle(self.booking())
            second_returned.set()
            return result

        with patch.object(self.service.idempotency, "remember", side_effect=paused_remember):
            with ThreadPoolExecutor(max_workers=2) as executor:
                first = executor.submit(self.backend.handle, self.booking())
                try:
                    self.assertTrue(saving.wait(3))
                    second = executor.submit(duplicate)
                    self.assertTrue(second_started.wait(3))
                    self.assertFalse(second_returned.wait(0.1), "duplicate escaped before replay save completed")
                finally:
                    release.set()
                first_result, second_result = first.result(timeout=3), second.result(timeout=3)
        self.assertEqual(first_result.status, 201)
        self.assertEqual(second_result.body, first_result.body)
        self.assertEqual(len(self.appointments.list()), 1)
        self.assertEqual(len(self.tasks.list()), 1)
        self.assertEqual(len(self.replays.list()), 1)

    def test_concurrent_different_keys_cannot_overbook_single_capacity(self):
        start = Barrier(8)

        def attempt(index):
            start.wait(timeout=3)
            return self.backend.handle(self.booking(patient=f"P-CARDIO-{index}", key=f"CARDIO-{index}"))

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(attempt, range(8)))
        self.assertEqual(sorted(result.status for result in results), [201] + [409] * 7)
        self.assertTrue(all(
            result.status == 201 or result.body["error"]["code"] == "SLOT_NOT_AVAILABLE"
            for result in results
        ))
        self.assertEqual(len(self.appointments.list()), 1)
        self.assertEqual(len(self.tasks.list()), 1)
        self.assertEqual(len(self.replays.list()), 1)


if __name__ == "__main__":
    unittest.main()
