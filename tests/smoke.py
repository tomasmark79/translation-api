"""Exercise the installed executable against a local fake Ollama server."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import socket
import subprocess
import sys
import threading
import time
from urllib.request import Request, urlopen


class OllamaStub(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_GET(self):
        assert self.path == "/api/tags"
        body = json.dumps({"models": [{"name": "translategemma:4b"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        assert self.path == "/api/chat"
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        assert data["messages"][-1]["content"] == "Ahoj."
        body = b'{"message":{"content":"Hello."},"done":false}\n'
        body += b'{"done":true,"done_reason":"stop"}\n'
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def request(url, data=None):
    body = json.dumps(data).encode() if data is not None else None
    with urlopen(Request(url, body, {"Content-Type": "application/json"}), timeout=2) as response:
        return response.status, json.load(response)


def main():
    ollama = ThreadingHTTPServer(("127.0.0.1", 0), OllamaStub)
    thread = threading.Thread(target=ollama.serve_forever, daemon=True)
    thread.start()
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen([
        sys.argv[1], "--port", str(port),
        "--ollama-url", f"http://127.0.0.1:{ollama.server_port}",
    ])
    url = f"http://127.0.0.1:{port}"
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise AssertionError(f"API exited: {process.returncode}")
            try:
                _, health = request(url + "/health")
                break
            except OSError:
                time.sleep(0.05)
        else:
            raise AssertionError("API did not become ready")
        assert health == {"status": "ready", "backend": "ollama",
                          "model": "translategemma:4b", "device": "ollama"}, health
        for text, expected in [
            ("Ahoj. ", "Hello."),
            ("Ahoj.\n \ufeff", "Hello.\n "),
            ("Ahoj.\n \u200b\ufeff", "Hello.\n "),
        ]:
            status, job = request(url + "/translate", {"q": text, "source": "cs", "target": "en"})
            assert status == 202, status
            for _ in range(100):
                _, result = request(url + "/translations/" + job["jobId"])
                if result["status"] != "pending":
                    break
                time.sleep(0.01)
            assert result["status"] == "done", result
            assert result["translatedText"] == expected, result
        print("Installed CLI, health, async translation, trailing whitespace and editor placeholders: OK")

    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        ollama.shutdown()
        ollama.server_close()
        thread.join()


if __name__ == "__main__":
    main()
