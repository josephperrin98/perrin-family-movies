"""Tests for the family PIN comparison and member seeding in identity.py."""

import unittest

from identity import DEMO_MEMBERS, members_to_seed, pin_matches


class TestPinMatches(unittest.TestCase):
    def test_correct_pin(self):
        self.assertTrue(pin_matches("dimanche-soir", "dimanche-soir"))

    def test_wrong_pin(self):
        self.assertFalse(pin_matches("dimanche-matin", "dimanche-soir"))

    def test_empty_entry(self):
        self.assertFalse(pin_matches("", "dimanche-soir"))

    def test_no_pin_configured_never_matches(self):
        self.assertFalse(pin_matches("anything", None))

    def test_non_ascii_pin(self):
        self.assertTrue(pin_matches("Chloé-🎬", "Chloé-🎬"))


class TestMembersToSeed(unittest.TestCase):
    def test_no_config_falls_back_to_demo(self):
        self.assertEqual(members_to_seed(None), DEMO_MEMBERS)
        self.assertEqual(members_to_seed([]), DEMO_MEMBERS)

    def test_configured_members_are_used(self):
        configured = [{"username": "dan", "display_name": "Dan", "avatar_emoji": "🚲"}]
        self.assertEqual(members_to_seed(configured), configured)

    def test_missing_emoji_gets_default(self):
        seeded = members_to_seed([{"username": "eve", "display_name": "Eve"}])
        self.assertEqual(seeded[0]["avatar_emoji"], "👤")


if __name__ == "__main__":
    unittest.main()
