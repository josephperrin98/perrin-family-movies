import json
import unittest
from datetime import date
from unittest import mock

import anthropic
import httpx2

from summary.facts import RatingRow, compute_facts
from summary.writer import Colour, WriterError, build_payload, build_user_content, write_colour


def facts(until=None):
    rows = [RatingRow("Le Daim", "2019", "Comedy", "Bob", 6.0, "Le blouson !")]
    return compute_facts(2026, 9, rows, [], until=until)


def fake_response(colour, stop_reason="end_turn"):
    usage = mock.Mock(input_tokens=1200, output_tokens=300)
    return mock.Mock(parsed_output=colour, stop_reason=stop_reason, usage=usage)


class TestPayload(unittest.TestCase):
    def test_payload_shape(self):
        payload = build_payload(facts(), ["texte d'août"])
        self.assertEqual(payload["mois"], "septembre 2026")
        self.assertEqual(payload["palier"], "leger")
        self.assertEqual(payload["notes"][0]["qui"], "Bob")
        self.assertEqual(payload["notes"][0]["commentaire"], "Le blouson !")
        self.assertEqual(payload["deja_ecrit"], ["texte d'août"])
        self.assertIn("OSS 117", payload["classiques_famille"])
        self.assertEqual(payload["sans_note"], [])

    def test_extended_period_label(self):
        payload = build_payload(facts(until=date(2026, 10, 9)), [])
        self.assertEqual(payload["mois"], "septembre et début octobre 2026")

    def test_feedback_is_appended(self):
        content = build_user_content({"mois": "septembre 2026"}, ("brouillon", ["Ajoute au moins un emoji."]))
        self.assertIn('"mois": "septembre 2026"', content)
        self.assertIn("brouillon", content)
        self.assertIn("- Ajoute au moins un emoji.", content)

    def test_payload_is_sent_as_readable_json(self):
        content = build_user_content(build_payload(facts(), []), None)
        self.assertEqual(json.loads(content)["notes"][0]["film"], "Le Daim")


class TestWriteColour(unittest.TestCase):
    def test_returns_parsed_colour_and_tokens(self):
        colour = Colour(message="Salut 🎬 ?", titles_mentioned=[], names_mentioned=[])
        client = mock.Mock()
        client.messages.parse.return_value = fake_response(colour)
        result = write_colour(client, "claude-opus-5-5", {"mois": "x"})
        self.assertEqual(result.colour, colour)
        self.assertEqual((result.input_tokens, result.output_tokens), (1200, 300))
        kwargs = client.messages.parse.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertIs(kwargs["output_format"], Colour)
        self.assertEqual(kwargs["output_config"], {"effort": "medium"})

    def test_refusal_gives_no_colour(self):
        client = mock.Mock()
        client.messages.parse.return_value = fake_response(None, stop_reason="refusal")
        self.assertIsNone(write_colour(client, "m", {}).colour)

    def test_api_error_becomes_writer_error(self):
        client = mock.Mock()
        request = httpx2.Request("POST", "https://api.anthropic.com/v1/messages")
        client.messages.parse.side_effect = anthropic.APIConnectionError(request=request)
        with self.assertRaises(WriterError):
            write_colour(client, "m", {})


if __name__ == "__main__":
    unittest.main()
