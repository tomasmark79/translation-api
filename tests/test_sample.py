"""Exercise the sample command against a local Ollama stub."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import redirect_stderr
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from server import Jobs, make_server
from scripts.translate_sample import translate_api

ROOT = Path(__file__).resolve().parents[1]


class SampleTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        calls = self.calls
        class OllamaStub(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def reply(self, body):
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                calls.append(self.path)
                self.reply(json.dumps({"models": [{"name": "sample:test"}]}).encode())

            def do_POST(self):
                data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                calls.append((self.path, data))
                text = {"Dobrý den.": "Good day.", "Druhá věta.": "Second sentence."}[data["messages"][-1]["content"]]
                self.reply((json.dumps({"message": {"content": text}}) + "\n" +
                            json.dumps({"done": True, "done_reason": "stop"}) + "\n").encode())

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), OllamaStub)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temporary = tempfile.TemporaryDirectory(prefix="translation-sample-test-")
        self.file = Path(self.temporary.name) / "czech.txt"
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temporary.cleanup()

    def run_sample(self, *options):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "translate_sample.py"),
                               "--ollama-url", self.url, "--model", "sample:test",
                               "--file", str(self.file), *options],
                              cwd=self.temporary.name, capture_output=True, text=True, timeout=10)

    def test_sample_is_nonblank_and_fits_the_api_limit(self):
        text = (ROOT / "samples" / "babicka-cs.txt").read_text(encoding="utf-8")
        self.assertTrue(text.startswith("Babička měla syna a dvě dcery."))
        self.assertLessEqual(len(text), 10000)
        self.assertGreater(len(text), 8000)

    def test_command_uses_selected_server_model_and_shared_translation_pipeline(self):
        self.file.write_text("Dobrý den.\n\nDruhá věta.", encoding="utf-8")
        result = self.run_sample()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn(self.url, result.stderr)
        self.assertIn("sample:test", result.stderr)
        self.assertIn("Completed in", result.stderr)
        self.assertEqual(self.calls[0], "/api/tags")
        self.assertEqual(len(self.calls), 3)
        for path, request in self.calls[1:]:
            self.assertEqual(path, "/api/chat")
            self.assertEqual(request["model"], "sample:test")
            self.assertIn("from Czech into English", request["messages"][0]["content"])

    def test_invalid_input_is_rejected_before_contacting_ollama(self):
        for text in [" \n", "a" * 10001]:
            with self.subTest(length=len(text)):
                self.file.write_text(text, encoding="utf-8")
                result = self.run_sample()
                self.assertEqual(result.returncode, 1)
                self.assertEqual(result.stdout, "")
                self.assertIn("10,000", result.stderr)
                self.assertEqual(self.calls, [])

    def test_unavailable_model_is_reported_without_translation_output(self):
        self.file.write_text("Dobrý den.", encoding="utf-8")
        result = self.run_sample("--model", "missing:model")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("Model missing:model is not available", result.stderr)
        self.assertEqual(self.calls, ["/api/tags"])


class ApiProgressTests(unittest.TestCase):
    def test_queue_position_and_running_state_are_displayed(self):
        responses = [
            {"backend": "ollama", "model": "server:model"}, {"jobId": "a" * 32},
            {"status": "pending", "state": "queued", "queuePosition": 2},
            {"status": "pending", "state": "queued", "queuePosition": 1},
            {"status": "pending", "state": "running", "queuePosition": 0, "partialText": "Good"},
            {"status": "done", "translatedText": "Good day."},
        ]
        output, progress = StringIO(), []
        with patch("scripts.translate_sample.api_request", side_effect=responses), \
             patch("scripts.translate_sample.time.sleep"), redirect_stderr(output):
            self.assertEqual(translate_api("http://api", "Dobrý den.", progress.append)["translatedText"], "Good day.")
        self.assertIn("Queued: position 2", output.getvalue())
        self.assertIn("Queued: position 1", output.getvalue())
        self.assertIn("Running…", output.getvalue())
        self.assertEqual(progress[-1], "Good")

    def test_keyboard_interrupt_cancels_the_submitted_job(self):
        responses = [{"model": "test"}, {"jobId": "a" * 32}, KeyboardInterrupt(), {"status": "cancelled"}]
        with patch("scripts.translate_sample.api_request", side_effect=responses) as request, \
             redirect_stderr(StringIO()) as output:
            with self.assertRaises(KeyboardInterrupt):
                translate_api("http://api/", "Dobrý den.", lambda _: None)
        self.assertEqual(request.call_args.args, ("http://api/translations/" + "a" * 32,))
        self.assertEqual(request.call_args.kwargs, {"method": "DELETE"})
        self.assertIn("cancelled on the server", output.getvalue())

    def test_interrupt_reports_running_job_cannot_be_cancelled(self):
        responses = [{"model": "test"}, {"jobId": "a" * 32}, KeyboardInterrupt(),
                     RuntimeError("Translation API HTTP 409: Only queued translations can be cancelled.")]
        with patch("scripts.translate_sample.api_request", side_effect=responses), \
             redirect_stderr(StringIO()) as output:
            with self.assertRaises(KeyboardInterrupt):
                translate_api("http://api", "Dobrý den.", lambda _: None)
        self.assertIn("Could not cancel server job", output.getvalue())
        self.assertNotIn("cancelled on the server", output.getvalue())

    def test_cancelled_job_is_reported(self):
        with patch("scripts.translate_sample.api_request", side_effect=[
            {"model": "test"}, {"jobId": "a" * 32}, {"status": "cancelled"},
        ]), redirect_stderr(StringIO()):
            with self.assertRaisesRegex(RuntimeError, "was cancelled"):
                translate_api("http://api", "Dobrý den.", lambda _: None)


class ApiSampleTests(unittest.TestCase):
    def setUp(self):
        class Translator:
            model = "server:model"
            fail = False

            def language(self, code):
                return code

            def translate(self, text, source, target, on_progress):
                self.received = (text, source, target)
                if self.fail:
                    raise RuntimeError("Upstream model failed")
                return {"translatedText": "Good day.", "detectedLanguage": {"language": source}}

        self.translator = Translator()
        self.jobs = Jobs(self.translator)
        self.server = make_server(0, self.jobs)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.temporary = tempfile.TemporaryDirectory(prefix="translation-api-sample-test-")
        self.file = Path(self.temporary.name) / "czech.txt"
        self.file.write_text("Dobrý den.", encoding="utf-8")
        self.url = f"http://127.0.0.1:{self.server.server_port}/"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.jobs.executor.shutdown()
        self.temporary.cleanup()

    def run_sample(self, *options):
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "translate_sample.py"),
                               "--api-url", self.url, "--file", str(self.file), *options],
                              capture_output=True, text=True, timeout=10)

    def test_api_job_uses_server_model_and_translates_to_english(self):
        result = self.run_sample()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertIn("Model: server:model", result.stderr)
        self.assertIn("Backend: ollama", result.stderr)
        self.assertIn("Completed in", result.stderr)
        self.assertEqual(self.translator.received, ("Dobrý den.", "cs", "en"))

    def test_failed_api_job_reports_error(self):
        self.translator.fail = True
        result = self.run_sample()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertIn("Upstream model failed", result.stderr)

    def test_api_model_override_and_mixed_endpoints_are_rejected(self):
        for options in [("--model", "other:model"), ("--ollama-url", self.url)]:
            with self.subTest(options=options):
                result = self.run_sample(*options)
                self.assertEqual(result.returncode, 2)
                self.assertEqual(result.stdout, "")
                self.assertEqual(self.jobs.jobs, {})

    def test_http_errors_are_reported_without_traceback(self):
        self.url += "wrong-path"
        result = self.run_sample()
        self.assertEqual(result.returncode, 1)
        self.assertIn("Translation API HTTP 404", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
