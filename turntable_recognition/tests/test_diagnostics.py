import io
import unittest
from contextlib import redirect_stderr

from diagnostics import exception_details, log_event


class DiagnosticsTests(unittest.TestCase):
    def test_http_details_include_status_url_and_redact_secret(self):
        class Response:
            status_code = 503
            url = "https://api.example.test/recognize"
            text = "temporary failure"

        class HttpError(Exception):
            response = Response()
            request = None

        details = exception_details(HttpError("failed token-secret"), secret="token-secret")
        self.assertEqual(details["http_status"], 503)
        self.assertEqual(details["url"], "https://api.example.test/recognize")
        self.assertNotIn("token-secret", str(details))
        self.assertIn("[redacted]", details["error"])

    def test_log_line_has_utc_timestamp_and_structured_fields(self):
        output = io.StringIO()
        with redirect_stderr(output):
            log_event("recognition_attempt_failed", level="ERROR", attempt_id=7,
                      reason="no_match")
        line = output.getvalue()
        self.assertRegex(line, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z ERROR ")
        self.assertIn('"attempt_id": 7', line)
        self.assertIn('"reason": "no_match"', line)


if __name__ == "__main__":
    unittest.main()

