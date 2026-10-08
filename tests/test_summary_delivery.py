import unittest
from unittest import mock
from urllib.parse import unquote

from summary.delivery import build_email, send_email, whatsapp_link

MESSAGE = "Salut la famille 🎬 !\n«Le Daim» & co… Qui vient ? 50% de chances"


class TestWhatsappLink(unittest.TestCase):
    def test_round_trip(self):
        link = whatsapp_link(MESSAGE)
        self.assertTrue(link.startswith("https://wa.me/?text="))
        self.assertEqual(unquote(link.removeprefix("https://wa.me/?text=")), MESSAGE)

    def test_special_characters_are_encoded(self):
        text = whatsapp_link(MESSAGE).removeprefix("https://wa.me/?text=")
        for raw in (" ", "&", "\n", "?"):
            self.assertNotIn(raw, text)
        self.assertIn("50%25", text)  # a literal % is encoded too


class TestEmail(unittest.TestCase):
    def test_email_has_text_and_html_with_link(self):
        msg = build_email("bot@gmail.com", "me@hotmail.fr", "Résumé Perrin-rama: Sept'26", MESSAGE)
        self.assertEqual(msg["Subject"], "Résumé Perrin-rama: Sept'26")
        self.assertEqual(msg["To"], "me@hotmail.fr")
        plain = msg.get_body(("plain",)).get_content()
        html = msg.get_body(("html",)).get_content()
        self.assertIn("Salut la famille", plain)
        self.assertIn("Envoyer sur WhatsApp", html)
        self.assertIn("&amp;", html)  # message text is HTML-escaped

    def test_send_uses_gmail_over_ssl(self):
        msg = build_email("bot@gmail.com", "me@hotmail.fr", "s", "m")
        with mock.patch("summary.delivery.smtplib.SMTP_SSL") as smtp:
            send_email(msg, "bot@gmail.com", "app-password")
        smtp.assert_called_once_with("smtp.gmail.com", 465, timeout=30)
        server = smtp.return_value.__enter__.return_value
        server.ehlo.assert_called_once_with()  # auth() doesn't greet the server itself
        mechanism, authobject = server.auth.call_args.args
        self.assertEqual(mechanism, "PLAIN")
        self.assertEqual(authobject(), "\0bot@gmail.com\0app-password")
        server.send_message.assert_called_once_with(msg)

    def test_spaces_in_app_password_are_removed(self):
        # Google displays app passwords as "abcd efgh ijkl mnop"
        msg = build_email("bot@gmail.com", "me@hotmail.fr", "s", "m")
        with mock.patch("summary.delivery.smtplib.SMTP_SSL") as smtp:
            send_email(msg, "bot@gmail.com", "abcd efgh ijkl mnop")
        server = smtp.return_value.__enter__.return_value
        self.assertEqual(server.auth.call_args.args[1](), "\0bot@gmail.com\0abcdefghijklmnop")


if __name__ == "__main__":
    unittest.main()
