import tempfile
import unittest
from datetime import datetime
from unittest.mock import patch

from mock_backends.core.clock import MACAU_TZ
from mock_backends.core.http import BackendRequest
from mock_backends.server import create_application


class LiveDemoFixtureTests(unittest.TestCase):
    def setUp(self):
        self.data_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.data_dir.cleanup)
        self.clock_patch = patch(
            "mock_backends.core.clock.AsiaMacauClock.now",
            return_value=datetime(2026, 10, 13, 23, 59, tzinfo=MACAU_TZ),
        )
        self.current_time = self.clock_patch.start()
        self.addCleanup(self.clock_patch.stop)
        self.router = create_application(self.data_dir.name)

    def request(self, method, path, query=None, body=None, key=None):
        headers = {
            "Authorization": "Bearer mock-user-token",
            "X-Patient-Id": "PAT-LIVE-DEMO",
        }
        if key:
            headers["Idempotency-Key"] = key
        return self.router.dispatch(BackendRequest(
            method=method,
            path=f"/mock/medical/v1{path}",
            query=query or {},
            body=body,
            headers=headers,
            request_id="REQ-LIVE-DEMO",
        ))

    def slots(self, service_id, first="2026-10-13", last="2026-10-27"):
        return self.request("GET", "/appointment-slots", query={
            "service_id": [service_id],
            "date_from": [first],
            "date_to": [last],
        })

    def test_default_application_offers_medical_services_and_future_slots_in_october(self):
        catalog = self.request("GET", "/appointment-services")
        self.assertEqual(catalog.status, 200)
        self.assertEqual(
            {service["id"] for service in catalog.body["data"]},
            {"SERVICE-US-001", "SERVICE-PT-001", "SERVICE-ECHO-001"},
        )
        for service in catalog.body["data"]:
            with self.subTest(service=service["id"]):
                response = self.slots(service["id"])
                self.assertEqual(response.status, 200)
                self.assertEqual(
                    {slot["start"][:10] for slot in response.body["data"]},
                    {"2026-10-14", "2026-10-15", "2026-10-16"},
                )
                self.assertTrue(all(
                    datetime.fromisoformat(slot["start"]) > self.current_time.return_value
                    for slot in response.body["data"]
                ))

    def test_live_slot_date_and_consumed_capacity_survive_restart_and_midnight(self):
        offered = self.slots("SERVICE-PT-001", "2026-10-14", "2026-10-14")
        self.assertEqual(offered.status, 200)
        slot = next((slot for slot in offered.body["data"] if slot["id"] == "SLOT-PT-20261014-1000"), None)
        self.assertIsNotNone(slot)
        booked = self.request("POST", "/appointments", key="LIVE-PT-1", body={
            "patient_id": "PAT-LIVE-DEMO",
            "service_id": "SERVICE-PT-001",
            "slot_id": slot["id"],
            "referring_appointment_id": "APT-REF-DEMO",
            "consent": True,
        })
        self.assertEqual(booked.status, 201)
        self.assertEqual(booked.body["data"]["start"], "2026-10-14T10:00:00+08:00")
        self.current_time.return_value = datetime(2026, 10, 14, 0, 1, tzinfo=MACAU_TZ)
        self.router = create_application(self.data_dir.name)
        refreshed = self.slots("SERVICE-PT-001", "2026-10-14", "2026-10-14")
        same_slot = next((item for item in refreshed.body["data"] if item["id"] == slot["id"]), None)
        self.assertIsNotNone(same_slot)
        self.assertEqual(same_slot["start"], "2026-10-14T10:00:00+08:00")
        self.assertEqual(same_slot["remaining"], 1)
        stored = self.request("GET", f"/appointments/{booked.body['data']['id']}")
        self.assertEqual(stored.body["data"]["start"], "2026-10-14T10:00:00+08:00")

    def test_default_application_offers_registration_slots_within_booking_window(self):
        response = self.request("GET", "/registration-slots", query={
            "department_id": ["DEPT-CARDIO"],
            "date": ["2026-10-14"],
            "session": ["morning"],
        })
        self.assertEqual(response.status, 200)
        self.assertEqual(
            {item["id"] for item in response.body["data"]},
            {"SLOT-REG-20261014-CARDIO-1030", "SLOT-REG-20261014-CARDIO-1100"},
        )
        outside = self.request("GET", "/registration-slots", query={
            "department_id": ["DEPT-CARDIO"], "date": ["2026-10-28"],
        })
        self.assertEqual(outside.status, 422)
        self.assertEqual(outside.body["error"]["code"], "BOOKING_WINDOW_EXCEEDED")


if __name__ == "__main__":
    unittest.main()
