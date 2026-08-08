"""Live medical demo inventory is seeded once without changing saved bookings."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from mock_backends.core.clock import FixedClock, MACAU_TZ
from mock_backends.core.http import BackendRequest
from mock_backends.core.persistence import JsonLinesTextRepository
from mock_backends.server import create_application


class MedicalDemoSeedTests(unittest.TestCase):
    def runtime_application(self, root, day=13):
        clock = FixedClock(datetime(2026, 10, day, 9, tzinfo=MACAU_TZ))
        with patch("mock_backends.server.AsiaMacauClock", return_value=clock):
            return create_application(root)

    def request(self, method, suffix, *, query=None, body=None):
        return BackendRequest(
            method=method,
            path=f"/mock/medical/v1{suffix}",
            headers={
                "Authorization": "Bearer mock-user-token",
                "X-Patient-Id": "P-DEMO-SEED",
                "Idempotency-Key": "DEMO-SEED-BOOKING",
            },
            query=query or {},
            body=body,
            request_id="REQ-DEMO-SEED",
        )

    def search(self, application, service_id="SERVICE-US-001"):
        return application.dispatch(self.request(
            "GET", "/appointment-slots",
            query={
                "service_id": [service_id],
                "date_from": ["2026-10-13"],
                "date_to": ["2026-10-27"],
            },
        ))

    def test_fresh_runtime_database_has_three_upcoming_slots_per_service(self):
        with tempfile.TemporaryDirectory() as directory:
            application = self.runtime_application(Path(directory))
            services = application.dispatch(self.request("GET", "/appointment-services"))
            self.assertEqual(
                {item["id"] for item in services.body["data"]},
                {"SERVICE-US-001", "SERVICE-PT-001", "SERVICE-ECHO-001"},
            )
            for service_id in ("SERVICE-US-001", "SERVICE-PT-001", "SERVICE-ECHO-001"):
                slots = self.search(application, service_id).body["data"]
                self.assertEqual(
                    {item["start"][:10] for item in slots},
                    {"2026-10-14", "2026-10-15", "2026-10-16"},
                )
            ultrasound = self.search(application).body["data"][0]
            self.assertEqual(ultrasound["id"], "SLOT-US-20260812-1400")
            self.assertEqual(ultrasound["end"], "2026-10-14T14:30:00+08:00")

    def test_restart_keeps_seed_dates_and_booked_capacity(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = self.runtime_application(root)
            slots = self.search(first).body["data"]
            self.assertEqual(len(slots), 3)
            chosen = slots[0]
            created = first.dispatch(self.request("POST", "/appointments", body={
                "patient_id": "P-DEMO-SEED",
                "service_id": "SERVICE-US-001",
                "slot_id": chosen["id"],
                "referring_appointment_id": "APT-DEMO-REF",
                "consent": True,
            }))
            self.assertEqual(created.status, 201)
            self.assertEqual(created.body["data"]["start"], "2026-10-14T14:00:00+08:00")
            appointments_file = root / "medical" / "appointments.txt"
            saved_bytes = appointments_file.read_bytes()

            restarted = self.runtime_application(root, day=14)
            available = restarted.dispatch(self.request(
                "GET", "/appointment-slots",
                query={
                    "service_id": ["SERVICE-US-001"],
                    "date_from": ["2026-10-14"],
                    "date_to": ["2026-10-28"],
                },
            )).body["data"]
            self.assertEqual(
                {item["start"] for item in available},
                {"2026-10-15T09:30:00+08:00", "2026-10-16T15:00:00+08:00"},
            )
            self.assertNotIn(chosen["id"], {item["id"] for item in available})
            self.assertEqual(appointments_file.read_bytes(), saved_bytes)

    def test_existing_legacy_bookings_are_not_rebased(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            appointments_file = root / "medical" / "appointments.txt"
            JsonLinesTextRepository(appointments_file).insert({
                "id": "APT-LEGACY",
                "patient_id": "P-DEMO-SEED",
                "slot_id": "SLOT-US-20260812-1400",
                "status": "confirmed",
                "start": "2026-08-12T14:00:00+08:00",
                "end": "2026-08-12T14:30:00+08:00",
            })
            saved_bytes = appointments_file.read_bytes()
            application = self.runtime_application(root)
            detail = application.dispatch(self.request("GET", "/appointments/APT-LEGACY"))
            self.assertEqual(detail.body["data"]["start"], "2026-08-12T14:00:00+08:00")
            self.assertEqual(self.search(application).body["data"], [])
            self.assertEqual(appointments_file.read_bytes(), saved_bytes)
            self.assertFalse((root / "medical" / "slot_seed.txt").exists())


if __name__ == "__main__":
    unittest.main()
