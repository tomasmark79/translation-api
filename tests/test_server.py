import json
from io import BytesIO
from pathlib import Path
import sys
import threading
import time
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server import Jobs, OllamaTranslator, make_server, normalize_translation_text, request_stream, split_text
from unittest.mock import patch


class FakeTranslator:
    model = "test"
    def language(self, code):
        if code not in ("en", "cs", "de"):
            raise ValueError("Unsupported language")
        return code

    def translate(self, q, source, target, on_progress=None):
        if q == "fail":
            raise ValueError("Model error")
        if on_progress:
            on_progress("Ah")
        return {"translatedText": "Ahoj", "detectedLanguage": {"language": "eng_Latn"}}


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.jobs = Jobs(FakeTranslator())
        self.server = make_server(0, self.jobs)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.jobs.executor.shutdown()

    def request(self, path, data=None, headers=None, method=None):
        headers = {"Content-Type": "application/json", **(headers or {})}
        req = Request(self.url + path, data=json.dumps(data).encode() if data is not None else None,
                      headers=headers, method=method)
        try:
            response = urlopen(req, timeout=2)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def result(self, job_id):
        for _ in range(100):
            status, body = self.request("/translations/" + job_id)
            if body["status"] != "pending":
                return status, body
            time.sleep(.01)
        self.fail("The job did not finish")

    def test_translation_and_health(self):
        self.assertEqual(self.request("/health")[1]["status"], "ready")
        status, body = self.request("/translate", {"q": "Hello"})
        self.assertEqual(status, 202)
        status, result = self.result(body["jobId"])
        self.assertEqual(status, 200)
        self.assertEqual(result["translatedText"], "Ahoj")

    def test_external_clients_choose_target_and_default_to_auto_source(self):
        received = []
        def translate(q, source, target, on_progress):
            received.append((source, target))
            return {"translatedText": f"Translation into {target}"}
        self.jobs.translator.translate = translate
        for target in ["cs", "en", "de"]:
            with self.subTest(target=target):
                status, job = self.request("/translate", {"q": "Hello", "target": target})
                self.assertEqual(status, 202)
                result = self.result(job["jobId"])[1]
                self.assertEqual(result["translatedText"], f"Translation into {target}")
                self.assertEqual(received[-1], ("auto", target))
        self.assertEqual(self.request("/translate", {"q": "Hello", "target": "auto"})[0], 400)

    def test_http_normalizes_blank_lines_and_rejects_placeholder_only_input(self):
        received = []
        def translate(q, source, target, on_progress):
            received.append(q)
            return {"translatedText": "Hello.\n "}
        self.jobs.translator.translate = translate
        status, job = self.request("/translate", {"q": "Ahoj.\n \ufeff\u200b"})
        self.assertEqual(status, 202)
        self.assertEqual(self.result(job["jobId"])[1]["status"], "done")
        self.assertEqual(received, ["Ahoj.\n "])
        for q in ["\n \ufeff\u200b", "\ufeff" * 10001]:
            with self.subTest(q_length=len(q)):
                self.assertEqual(self.request("/translate", {"q": q})[0], 400)
        self.assertEqual(len(received), 1)

    def test_partial_result_while_pending(self):
        started = threading.Event()
        finish = threading.Event()
        def slow_translate(q, source, target, on_progress):
            on_progress("Průběžný")
            started.set()
            finish.wait(2)
            return {"translatedText": "Průběžný překlad"}
        self.jobs.translator.translate = slow_translate
        try:
            _, body = self.request("/translate", {"q": "Hello"})
            self.assertTrue(started.wait(1))
            _, pending = self.request("/translations/" + body["jobId"])
            self.assertEqual(pending, {"status": "pending", "state": "running",
                                       "queuePosition": 0, "partialText": "Průběžný"})
        finally:
            finish.set()
        self.assertEqual(self.result(body["jobId"])[1]["translatedText"], "Průběžný překlad")

    def test_browser_extension_origins(self):
        for origin in [
            "chrome-extension://" + "a" * 32,
            "moz-extension://01234567-89ab-4cde-8fab-0123456789ab",
        ]:
            with self.subTest(origin=origin):
                headers = {"Origin": origin}
                self.assertEqual(self.request("/health", headers=headers)[0], 200)
                status, body = self.request("/translate", {"q": "Hello"}, headers)
                self.assertEqual(status, 202)
                path = "/translations/" + body["jobId"]
                self.assertEqual(self.request(path, headers=headers)[0], 200)
                self.assertEqual(self.result(body["jobId"])[1]["translatedText"], "Ahoj")

    def test_invalid_origins_are_rejected(self):
        for origin in [
            "https://discord.com", "http://127.0.0.1:5001", "null",
            "chrome-extension://" + "z" * 32,
            "moz-extension://not-a-uuid",
            "moz-extension://01234567-89ab-4cde-8fab-0123456789ab.evil.example",
            "moz-extension://01234567-89ab-4cde-8fab-0123456789ab/",
        ]:
            with self.subTest(origin=origin):
                headers = {"Origin": origin}
                self.assertEqual(self.request("/health", headers=headers)[0], 403)
                self.assertEqual(self.request("/translate", {"q": "Hello"}, headers)[0], 403)
                self.assertEqual(self.request("/translations/" + "a" * 32, headers=headers)[0], 403)

    def test_model_error(self):
        _, body = self.request("/translate", {"q": "fail"})
        self.assertEqual(self.result(body["jobId"])[1]["status"], "failed")

    def test_bad_inputs(self):
        for data in [[], {"q": ""}, {"q": "x" * 10001}, {"q": "Hello", "target": "xx"}, {"q": "Hello", "source": []}]:
            with self.subTest(data=str(data)[:50]):
                self.assertEqual(self.request("/translate", data)[0], 400)
        self.assertEqual(self.request("/translations/" + "a" * 32)[0], 404)
        self.assertEqual(self.request("/translate", {"q": "Hello"}, {"Origin": "https://example.com"})[0], 403)
        self.assertEqual(self.request("/translate", {"q": "Hello"}, {"Content-Type": "text/plain"})[0], 415)

    def test_bounded_queue(self):
        event = threading.Event()
        self.jobs.translator.translate = lambda *args: event.wait(2)
        try:
            for _ in range(8):
                self.assertEqual(self.request("/translate", {"q": "Hello"})[0], 202)
            self.assertEqual(self.request("/translate", {"q": "Hello"})[0], 429)
        finally:
            event.set()

    def test_queue_positions_cancellation_capacity_and_execution_order(self):
        started, finish = threading.Event(), threading.Event()
        received = []
        def translate(q, source, target, on_progress):
            received.append(q)
            started.set()
            self.assertTrue(finish.wait(5))
            return {"translatedText": q}
        self.jobs.translator.translate = translate
        try:
            _, first = self.request("/translate", {"q": "Running"})
            self.assertTrue(started.wait(1))
            path = "/translations/" + first["jobId"]
            self.assertEqual(self.request(path)[1]["state"], "running")
            self.assertEqual(self.request(path, method="DELETE")[0], 409)
            queued = [self.request("/translate", {"q": f"Queued {i}"})[1] for i in range(7)]
            for position, job in enumerate(queued, 1):
                self.assertEqual(job["state"], "queued")
                self.assertEqual(job["queuePosition"], position)
                self.assertEqual(self.request("/translations/" + job["jobId"])[1]["queuePosition"], position)
            self.assertEqual(self.request("/translate", {"q": "Overflow"})[0], 429)
            cancelled_path = "/translations/" + queued[0]["jobId"]
            self.assertEqual(self.request(cancelled_path, method="DELETE"), (200, {"status": "cancelled"}))
            self.assertEqual(self.request(cancelled_path, method="DELETE")[0], 200)
            self.assertEqual(self.request(cancelled_path)[1], {"status": "cancelled"})
            self.assertEqual(self.request("/translations/" + queued[1]["jobId"])[1]["queuePosition"], 1)
            status, extra = self.request("/translate", {"q": "Replacement"})
            self.assertEqual(status, 202)
            self.assertEqual(extra["queuePosition"], 7)
        finally:
            finish.set()
        self.assertEqual(self.result(extra["jobId"])[1]["status"], "done")
        self.assertEqual(received, ["Running", *[f"Queued {i}" for i in range(1, 7)], "Replacement"])
        self.assertEqual(self.request(path, method="DELETE")[0], 409)

    def test_cancel_rejects_missing_jobs_invalid_paths_and_web_origins(self):
        path = "/translations/" + "a" * 32
        self.assertEqual(self.request(path, method="DELETE")[0], 404)
        self.assertEqual(self.request("/translate", method="DELETE")[0], 404)
        self.assertEqual(self.request(path, method="DELETE", headers={"Origin": "https://example.com"})[0], 403)

    def test_chunking_does_not_lose_text(self):
        for text in ["A sentence. " * 200, "連続した文字列" * 300, "one " + "x" * 2000]:
            chunks = split_text(text, len, 100)
            self.assertEqual("".join(chunks), text)
            self.assertTrue(all(len(chunk) <= 100 for chunk in chunks))


class JobLifetimeTests(unittest.TestCase):
    def test_cancelled_job_retention_starts_at_cancellation(self):
        jobs = Jobs(FakeTranslator())
        started, finish = threading.Event(), threading.Event()
        def translate(*args):
            started.set()
            finish.wait(5)
            return {"translatedText": "Finished"}
        jobs.translator.translate = translate
        try:
            jobs.submit({"q": "Blocking"})
            self.assertTrue(started.wait(1))
            with patch("server.time.monotonic", return_value=1000):
                job_id = jobs.submit({"q": "Cancel me"})["jobId"]
                jobs.cancel(job_id)
            with patch("server.time.monotonic", return_value=1599):
                jobs.submit({"q": "Still retained"})
                self.assertEqual(jobs.get(job_id)["status"], "cancelled")
            with patch("server.time.monotonic", return_value=1601):
                jobs.submit({"q": "After expiration"})
                with self.assertRaises(KeyError):
                    jobs.get(job_id)
        finally:
            finish.set()
            jobs.executor.shutdown()

    def test_retention_starts_after_completion_even_for_long_or_failed_jobs(self):
        for fail in [False, True]:
            with self.subTest(fail=fail):
                clock = [0]
                jobs = Jobs(FakeTranslator())
                def translate(q, source, target, on_progress):
                    if q == "Long text":
                        clock[0] = 1000
                        if fail:
                            raise ValueError("Model error")
                    return {"translatedText": "Finished"}
                jobs.translator.translate = translate
                try:
                    with patch("server.time.monotonic", side_effect=lambda: clock[0]):
                        job_id = jobs.submit({"q": "Long text"})["jobId"]
                        future = jobs.jobs[job_id]["future"]
                        if fail:
                            with self.assertRaisesRegex(ValueError, "Model error"):
                                future.result(timeout=2)
                        else:
                            future.result(timeout=2)
                        clock[0] = 1001
                        other_id = jobs.submit({"q": "Next"})["jobId"]
                        jobs.jobs[other_id]["future"].result(timeout=2)
                        self.assertEqual(jobs.get(job_id)["status"], "failed" if fail else "done")
                        clock[0] = 1599
                        other_id = jobs.submit({"q": "Still retained"})["jobId"]
                        jobs.jobs[other_id]["future"].result(timeout=2)
                        self.assertIn(job_id, jobs.jobs)
                        clock[0] = 1601
                        jobs.submit({"q": "After expiration"})
                        with self.assertRaises(KeyError):
                            jobs.get(job_id)
                finally:
                    jobs.executor.shutdown()


class OllamaTests(unittest.TestCase):
    def test_stream_allows_ten_minutes_for_network_reads(self):
        response = BytesIO(b'{"done": true, "done_reason": "stop", "message": {"content": "Hello"}}\n')
        pieces = []
        with patch("server.urlopen", return_value=response) as open_url:
            request_stream("http://127.0.0.1:11434/api/chat", {}, pieces.append)
        self.assertEqual(open_url.call_args.kwargs["timeout"], 600)
        self.assertEqual(pieces, ["Hello"])

    def test_auto_detection_and_german_target_use_human_readable_names(self):
        requests = []
        def fake_stream(url, data, on_piece, timeout=120):
            requests.append(data)
            on_piece("Guten Morgen.")
        with patch("server.request_json", return_value={"models": [{"name": "translategemma:4b"}]}), \
             patch("server.request_stream", fake_stream), patch("langdetect.detect", return_value="en") as detect:
            translator = OllamaTranslator("translategemma:4b", "http://127.0.0.1:11434")
            result = translator.translate("Good morning.\n \ufeff", "auto", "de")
        detect.assert_called_once_with("Good morning.\n ")
        self.assertIn("from English into German", requests[0]["messages"][0]["content"])
        self.assertEqual(result["translatedText"], "Guten Morgen.\n ")

    def test_blank_line_placeholders_never_reach_ollama(self):
        requests = []
        def fake_stream(url, data, on_piece, timeout=120):
            requests.append(data["messages"][1]["content"])
            on_piece("Hello.")
        with patch("server.request_json", return_value={"models": [{"name": "translategemma:4b"}]}), \
             patch("server.request_stream", fake_stream):
            translator = OllamaTranslator("translategemma:4b", "http://127.0.0.1:11434")
            for marker in ["\ufeff", "\u200b", "\ufeff\u200b"]:
                with self.subTest(marker=repr(marker)):
                    requests.clear()
                    progress = []
                    result = translator.translate("Ahoj.\n " + marker + "\nAhoj.", "cs", "en", progress.append)
                    self.assertEqual(requests, ["Ahoj.", "Ahoj."])
                    self.assertEqual(result["translatedText"], "Hello.\n \nHello.")
                    self.assertEqual(progress[-1], result["translatedText"])

    def test_ndjson_stream_emits_pieces_and_requires_completion(self):
        pieces = []
        payload = b''.join(json.dumps(item).encode() + b'\n' for item in [
            {"message": {"content": "Ah"}, "done": False},
            {"message": {"content": "oj"}, "done": False},
            {"done": True, "done_reason": "stop"},
        ])
        with patch("server.urlopen", return_value=BytesIO(payload)):
            request_stream("http://localhost/api/chat", {"stream": True}, pieces.append)
        self.assertEqual(pieces, ["Ah", "oj"])
        with patch("server.urlopen", return_value=BytesIO(payload.split(b'{"done": true')[0])):
            with self.assertRaisesRegex(RuntimeError, "before the translation was complete"):
                request_stream("http://localhost/api/chat", {"stream": True}, pieces.append)

    def test_translation_uses_local_ollama_and_preserves_sentences(self):
        requests = []

        def fake_request(url, data=None, timeout=5):
            requests.append((url, data))
            return {"models": [{"name": "qwen3:8b"}]}

        def fake_stream(url, data, on_piece, timeout=120):
            requests.append((url, data))
            on_piece("Přelo")
            on_piece("ženo.")

        progress = []
        with patch("server.request_json", fake_request), patch("server.request_stream", fake_stream):
            translator = OllamaTranslator("qwen3:8b", "http://127.0.0.1:11434")
            result = translator.translate("Hello. Goodbye.", "en", "cs", progress.append)
        self.assertEqual(result["translatedText"], "Přeloženo. Přeloženo.")
        self.assertEqual(len(requests), 3)
        self.assertEqual(requests[1][1]["model"], "qwen3:8b")
        self.assertFalse(requests[1][1]["think"])
        self.assertTrue(requests[1][1]["stream"])
        self.assertEqual(requests[1][1]["messages"][1]["content"], "Hello.")
        self.assertIn("into Czech", requests[1][1]["messages"][0]["content"])
        self.assertEqual(progress[-1], "Přeloženo. Přeloženo.")

    def test_ollama_translates_czech_into_english(self):
        requests = []
        def fake_stream(url, data, on_piece, timeout=120):
            requests.append(data)
            on_piece("Hello.")
        with patch("server.request_json", return_value={"models": [{"name": "translategemma:4b"}]}), \
             patch("server.request_stream", fake_stream):
            translator = OllamaTranslator("translategemma:4b", "http://127.0.0.1:11434")
            result = translator.translate("Ahoj.", "cs", "en")
        self.assertEqual(result["translatedText"], "Hello.")
        self.assertIn("from Czech into English", requests[0]["messages"][0]["content"])

    def test_trailing_space_does_not_send_empty_text_to_ollama(self):
        requests = []
        def fake_stream(url, data, on_piece, timeout=120):
            text = data["messages"][1]["content"]
            self.assertTrue(text.strip())
            requests.append(text)
            on_piece("Hello.")
        with patch("server.request_json", return_value={"models": [{"name": "translategemma:4b"}]}), \
             patch("server.request_stream", fake_stream):
            translator = OllamaTranslator("translategemma:4b", "http://127.0.0.1:11434")
            result = translator.translate("Ahoj. ", "cs", "en")
        self.assertEqual(requests, ["Ahoj."])
        self.assertEqual(result["translatedText"], "Hello.")

    def test_ollama_error_is_not_translation(self):
        def failed_stream(url, data, on_piece, timeout=120):
            on_piece("Částečný výstup")
            raise RuntimeError("Ollama did not complete the translation. Try a shorter text.")
        with patch("server.request_json", return_value={"models": [{"name": "qwen3:8b"}]}), \
             patch("server.request_stream", failed_stream):
            translator = OllamaTranslator("qwen3:8b", "http://127.0.0.1:11434")
            with self.assertRaisesRegex(RuntimeError, "did not complete"):
                translator.translate("Hello.", "en", "cs")


class NormalizationTests(unittest.TestCase):
    def test_preserves_whitespace_and_characters_in_nonempty_text(self):
        for text, expected in [
            ("Ahoj.\r\n \ufeff\u200b\r\nDalší.", "Ahoj.\r\n \r\nDalší."),
            ("Ahoj.\n\u00a0\u200b", "Ahoj.\n\u00a0"),
            ("  Ahoj.\n ", "  Ahoj.\n "),
            ("A\ufeffhoj\nمی\u200cروم\n\u200c", "A\ufeffhoj\nمی\u200cروم\n\u200c"),
        ]:
            with self.subTest(text=repr(text)):
                self.assertEqual(normalize_translation_text(text), expected)
                self.assertEqual(normalize_translation_text(expected), expected)


if __name__ == "__main__":
    unittest.main()
