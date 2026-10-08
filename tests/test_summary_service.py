import unittest
from datetime import date

from summary.delivery import MAX_MESSAGE_CHARS
from summary.facts import RatingRow, compute_facts
from summary.service import MAX_ATTEMPTS, generate_message, run_month
from summary.writer import Colour, WriterError, WriterResult

GOOD = ("Ce mois-ci, Chloé a plongé dans «Le Daim» et en est ressortie avec "
        "une soudaine envie de blouson en daim 🧥. Le reste de la famille jure qu'il "
        "n'en portera jamais. Qui l'accompagne au prochain ?")
BAD = "Trop court ?"


def facts():
    return compute_facts(2026, 9, [RatingRow("Le Daim", "2019", "Comedy", "Chloé", 8.0, None)], [])


def writer(*messages):
    """Fake writer returning the given messages in order; records the feedback it got."""
    calls = []

    def write(payload, feedback):
        calls.append(feedback)
        message = messages[len(calls) - 1]
        if isinstance(message, Exception):
            raise message
        colour = None if message is None else Colour(
            message=message, titles_mentioned=["Le Daim"] if "«" in message else [], names_mentioned=[])
        return WriterResult(colour, 1000, 200)

    write.calls = calls
    return write


class TestGenerateMessage(unittest.TestCase):
    def test_first_attempt_passes(self):
        result = generate_message(facts(), [], writer(GOOD))
        self.assertFalse(result.used_fallback)
        self.assertEqual(result.attempts, 1)
        self.assertEqual(result.colour_text, GOOD)
        self.assertTrue(result.full_message.startswith(GOOD))
        self.assertIn("«Le Daim» — Chloé 8,0", result.full_message)

    def test_retry_sends_draft_and_errors_back(self):
        write = writer(BAD, GOOD)
        result = generate_message(facts(), [], write)
        self.assertEqual(result.attempts, 2)
        self.assertIsNone(write.calls[0])
        draft, errors = write.calls[1]
        self.assertEqual(draft, BAD)
        self.assertTrue(errors)
        self.assertEqual(len(result.errors), 1)
        self.assertEqual((result.input_tokens, result.output_tokens), (2000, 400))

    def test_three_failures_fall_back(self):
        result = generate_message(facts(), [], writer(BAD, BAD, BAD))
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.attempts, MAX_ATTEMPTS)
        self.assertIsNone(result.colour_text)
        self.assertIn("septembre 2026", result.full_message)
        self.assertEqual(len(result.errors), 3)

    def test_refusal_counts_as_a_failed_attempt(self):
        result = generate_message(facts(), [], writer(None, GOOD))
        self.assertEqual(result.attempts, 2)
        self.assertFalse(result.used_fallback)

    def test_api_error_falls_back_immediately(self):
        result = generate_message(facts(), [], writer(WriterError("down")))
        self.assertTrue(result.used_fallback)
        self.assertEqual(result.attempts, 1)

    def test_biggest_message_fits_in_a_whatsapp_link(self):
        rows = [RatingRow(f"Un titre de film assez long numéro {i}", "2020", "Comedy, Drama",
                          f"Personne{i % 6}", 5 + i % 5, None) for i in range(30)]
        big = compute_facts(2026, 9, rows, [])
        colour = "x" * 900
        result = generate_message(big, [], lambda payload, feedback: WriterResult(
            Colour(message=colour, titles_mentioned=[], names_mentioned=[]), 0, 0))
        self.assertLessEqual(len(result.full_message), MAX_MESSAGE_CHARS)


class FakeStore:
    def __init__(self, rows=(), sent=False):
        self.rows, self.sent, self.saved, self.untils = list(rows), sent, [], []

    def month_rows(self, year, month, until=None):
        self.untils.append(until)
        return self.rows if (year, month) == (2026, 9) else []

    def summary_exists(self, year, month):
        return self.sent

    def previous_colour_texts(self, year, month, limit=3):
        return []

    def family_names(self):
        return ["Chloé", "Bob"]

    def save_summary(self, year, month, tier, generation, model):
        self.saved.append((year, month, tier, model))


class TestRunMonth(unittest.TestCase):
    def setUp(self):
        self.emails = []
        self.send = lambda subject, message: self.emails.append((subject, message))
        self.rows = [RatingRow("Le Daim", "2019", "Comedy", "Chloé", 8.0, None)]

    def test_sends_then_saves(self):
        store = FakeStore(self.rows)
        outcome = run_month(store, 2026, 9, writer(GOOD), self.send, "claude-opus-5-5")
        self.assertEqual(outcome.status, "sent")
        self.assertEqual(self.emails[0][0], "Résumé Perrin-rama: Sept'26")
        self.assertEqual(store.saved, [(2026, 9, "leger", "claude-opus-5-5")])

    def test_draft_naming_someone_who_did_not_rate_is_retried(self):
        # Bob is in the family (from the store) but rated nothing this month
        nudge = GOOD.replace("Qui l'accompagne", "Bob, tu l'accompagnes")
        write = writer(nudge, GOOD)
        outcome = run_month(FakeStore(self.rows), 2026, 9, write, self.send, "m", dry_run=True)
        self.assertEqual(outcome.generation.attempts, 2)
        self.assertTrue(any("Bob" in e for e in write.calls[1][1]))

    def test_until_widens_the_period_but_not_the_previous_month(self):
        store = FakeStore(self.rows)
        outcome = run_month(store, 2026, 9, writer(GOOD), self.send, "m", until=date(2026, 10, 9))
        self.assertEqual(outcome.subject, "Résumé Perrin-rama: Sept-Oct'26")
        self.assertEqual(store.untils, [date(2026, 10, 9), None])

    def test_already_sent_month_does_nothing(self):
        store = FakeStore(self.rows, sent=True)
        outcome = run_month(store, 2026, 9, writer(GOOD), self.send, "m")
        self.assertEqual(outcome.status, "already_sent")
        self.assertEqual((self.emails, store.saved), ([], []))

    def test_dry_run_neither_sends_nor_saves(self):
        store = FakeStore(self.rows, sent=True)
        outcome = run_month(store, 2026, 9, writer(GOOD), self.send, "m", dry_run=True)
        self.assertEqual(outcome.status, "dry_run")
        self.assertEqual((self.emails, store.saved), ([], []))

    def test_failed_email_saves_nothing(self):
        store = FakeStore(self.rows)

        def broken_send(subject, message):
            raise OSError("SMTP down")

        with self.assertRaises(OSError):
            run_month(store, 2026, 9, writer(GOOD), broken_send, "m")
        self.assertEqual(store.saved, [])


if __name__ == "__main__":
    unittest.main()
