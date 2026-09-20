"""Unit tests for SECNS.  Run with:  python -m unittest discover tests -v"""

import unittest

from secns import Orchestrator, make_packet
from secns.agents import DispatchAgent
from secns.config import EMS_NAME, INSTITUTIONAL_NAME


class TestTriage(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()

    def test_crash_is_tier_one(self):
        inc = self.orch.handle(make_packet("crash", 168, 11.2, 0, "road"))
        self.assertEqual(inc.severity, 100)
        self.assertEqual(inc.tier, 1)

    def test_score_is_reconstructible(self):
        """base 55 + HR 0 + impact 8 + no reply 12 = 75."""
        inc = self.orch.handle(make_packet("fall", 96, 4.1, 0, "home"))
        self.assertEqual(inc.severity, 55 + 0 + 8 + 12)
        self.assertEqual(len(inc.scoring_terms), 4)

    def test_self_cleared_low_severity_is_suppressed(self):
        inc = self.orch.handle(make_packet("fall", 96, 4.1, 1, "home"))
        self.assertTrue(inc.suppressed)
        self.assertEqual(inc.ranked_contacts, [])
        self.assertEqual(inc.messages, [])

    def test_self_cleared_high_severity_is_not_suppressed(self):
        """Saying 'I am OK' must not silence a genuinely critical event."""
        inc = self.orch.handle(make_packet("crash", 168, 11.2, 1, "road"))
        self.assertFalse(inc.suppressed)
        self.assertGreaterEqual(inc.severity, 45)

    def test_score_is_clamped(self):
        inc = self.orch.handle(make_packet("crash", 200, 19.0, 2, "road"))
        self.assertLessEqual(inc.severity, 100)


class TestPrioritisation(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()

    def test_ems_leads_tier_one(self):
        inc = self.orch.handle(make_packet("cardiac", 182, 0.2, 0, "home"))
        self.assertEqual(inc.ranked_contacts[0].name, EMS_NAME)

    def test_ems_absent_from_tier_three(self):
        inc = self.orch.handle(make_packet("inactive", 70, 0.0, 2, "home"))
        self.assertNotIn(EMS_NAME, [c.name for c in inc.ranked_contacts])

    def test_location_override_promotes_campus_security(self):
        on = self.orch.handle(make_packet("sos", 112, 0.0, 2, "campus"))
        off = self.orch.handle(make_packet("sos", 112, 0.0, 2, "home"))
        names_on = [c.name for c in on.ranked_contacts]
        names_off = [c.name for c in off.ranked_contacts]
        self.assertIn(INSTITUTIONAL_NAME, names_on)
        self.assertNotIn(INSTITUTIONAL_NAME, names_off)

    def test_tier_controls_notification_width(self):
        t1 = self.orch.handle(make_packet("crash", 168, 11.2, 0, "road"))
        t2 = self.orch.handle(make_packet("inactive", 58, 0.0, 0, "home"))
        self.assertEqual(len(t1.ranked_contacts), 4)
        self.assertEqual(len(t2.ranked_contacts), 3)

    def test_ranking_is_descending(self):
        inc = self.orch.handle(make_packet("fall", 150, 9.0, 0, "home"))
        weights = [c.weight for c in inc.ranked_contacts]
        self.assertEqual(weights, sorted(weights, reverse=True))


class TestComposerAndDispatch(unittest.TestCase):
    def setUp(self):
        self.orch = Orchestrator()
        self.inc = self.orch.handle(make_packet("cardiac", 182, 0.2, 0, "home"))

    def test_messages_are_role_specific(self):
        bodies = {m.contact: m.body for m in self.inc.messages}
        self.assertIn("EMERGENCY DISPATCH REQUEST", bodies[EMS_NAME])
        doctor = [b for n, b in bodies.items() if n.startswith("Dr.")]
        self.assertTrue(doctor and "Reply ACK to take the case" in doctor[0])

    def test_one_message_per_contact(self):
        self.assertEqual(len(self.inc.messages), len(self.inc.ranked_contacts))

    def test_acknowledgement_updates_status(self):
        target = self.inc.ranked_contacts[1].name
        DispatchAgent.acknowledge(self.inc, target)
        status = {c.name: c.status for c in self.inc.ranked_contacts}[target]
        self.assertEqual(status, "acknowledged")

    def test_silent_contacts_escalate(self):
        DispatchAgent.escalate(self.inc)
        self.assertTrue(all(c.status == "escalated" for c in self.inc.ranked_contacts))


class TestPerception(unittest.TestCase):
    def test_unknown_event_is_rejected(self):
        with self.assertRaises(ValueError):
            Orchestrator().handle(make_packet("earthquake", 90, 0.0, 0, "home"))


class TestAuditTrail(unittest.TestCase):
    def test_every_agent_logs(self):
        inc = Orchestrator().handle(make_packet("crash", 168, 11.2, 0, "road"))
        self.assertEqual(len(inc.trace), 6)
        self.assertEqual(inc.trace[0]["agent"], "Perception Agent")
        self.assertEqual(inc.trace[-1]["agent"], "Dispatch & Escalation Agent")


if __name__ == "__main__":
    unittest.main(verbosity=2)
