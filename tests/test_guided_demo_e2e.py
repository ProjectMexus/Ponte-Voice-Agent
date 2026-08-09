"""Guide evidence through the actual HTTP/MCP path, without paid model calls."""
import unittest
from tests import test_english_medical_demo_e2e as english_tests


class GuidedDemoEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.english = english_tests.EnglishMedicalDemoEndToEndTests()
        self.addCleanup(self.english.doCleanups)
        self.english.setUp()
        self.harness = self.english.harness

    def test_read_only_evidence_tracks_seven_turns_and_only_approval_writes(self):
        messages = [
            "Book a cardiology appointment next Tuesday afternoon", "Only after 3 PM",
            "Wait, do I have any other appointments?", "Will that clash with my existing appointments?",
            "Go back to the appointment we were booking", "The 3:30 PM one, please",
        ]
        replies = [self.harness.say(message) for message in messages]
        for reply in replies:
            self.assertEqual(reply['locale'], 'en')
            observation = reply['task']['facts']['demo_observation']
            self.assertEqual(observation['version'], 1)
            self.assertNotIn('medical.create_registration', observation['successful_reads'])
        self.assertIn('medical.list_departments', replies[0]['task']['facts']['demo_observation']['successful_reads'])
        self.assertIn('medical.search_registration_slots', replies[1]['task']['facts']['demo_observation']['successful_reads'])
        self.assertIn('medical.get_my_appointments', replies[2]['task']['facts']['demo_observation']['successful_reads'])
        self.assertEqual(replies[3]['task']['facts']['demo_observation']['control_action'], 'answer_question')
        self.assertEqual(replies[4]['task']['facts']['demo_observation']['control_action'], 'resume_booking')
        self.assertIn('medical.search_registration_slots', replies[4]['task']['facts']['demo_observation']['successful_reads'])
        state = self.harness.app.demo_workflow._states[replies[0]['task']['task_id']]
        self.assertNotIn('demo_observation', state.task['facts'])
        self.assertNotIn('demo_observation', str(state.transcript))
        self.english.assert_no_execution()
        action = next(a['event'] for a in replies[5]['workspace']['actions'] if a['event'].get('decision') == 'approve')
        confirmed = self.harness.interact(action)
        self.assertEqual(confirmed['receipt']['appointment']['time'], '15:30')
        self.assertEqual(len(self.english.live.write_dispatches()), 1)
        self.assertEqual(confirmed['task']['facts']['demo_observation']['successful_reads'], [])


if __name__ == '__main__':
    unittest.main()
