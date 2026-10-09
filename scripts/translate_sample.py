# Copyright (C) 2026 Tomáš Mark
# SPDX-License-Identifier: GPL-3.0-or-later

"""Translate the Czech book sample via Ollama or a Translation API server."""

import argparse
import json
from pathlib import Path
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from server import OllamaTranslator


def api_request(url, data=None, method=None):
    body = json.dumps(data).encode("utf-8") if data is not None else None
    request = Request(url, body, {"Content-Type": "application/json",
                                  "User-Agent": "translation-api/0.1.0"}, method=method)
    try:
        with urlopen(request, timeout=20) as response:
            return json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Translation API HTTP {error.code}: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"Translation API connection failed: {error.reason}") from error


def translate_api(url, text, on_progress):
    url = url.rstrip("/")
    health = api_request(url + "/health")
    print(f"Translation API: {url}\nBackend: {health.get('backend', 'unknown')}\n"
          f"Model: {health.get('model', 'unknown')}", file=sys.stderr, flush=True)
    print("Translating…", file=sys.stderr, flush=True)
    job = api_request(url + "/translate", {"q": text, "source": "cs", "target": "en"})
    if not isinstance(job.get("jobId"), str) or not job["jobId"]:
        raise ValueError("Translation API did not return a jobId.")
    job_url = url + "/translations/" + quote(job["jobId"], safe="")
    print(f"Job: {job['jobId']}", file=sys.stderr, flush=True)
    deadline = time.monotonic() + 900
    previous_state = None
    try:
        while time.monotonic() < deadline:
            result = api_request(job_url)
            status = result.get("status")
            if status == "done":
                if not isinstance(result.get("translatedText"), str):
                    raise ValueError("Translation API did not return translatedText.")
                return result
            if status == "failed":
                raise RuntimeError(result.get("error", "Translation API job failed."))
            if status == "cancelled":
                raise RuntimeError("The queued translation was cancelled.")
            if status != "pending":
                raise ValueError(f"Unknown Translation API job status: {status!r}")
            state = (result.get("state"), result.get("queuePosition"))
            if state != previous_state:
                if state[0] == "queued":
                    print(f"Queued: position {state[1]} (Ctrl+C to cancel).", file=sys.stderr, flush=True)
                elif state[0] == "running":
                    print("Running…", file=sys.stderr, flush=True)
                previous_state = state
            on_progress(result.get("partialText", ""))
            time.sleep(1)
        raise RuntimeError("Translation API job exceeded the 15-minute waiting limit.")
    except KeyboardInterrupt:
        try:
            api_request(job_url, method="DELETE")
            print("\nQueued translation cancelled on the server.", file=sys.stderr, flush=True)
        except (OSError, ValueError, RuntimeError) as error:
            print(f"\nCould not cancel server job: {error}", file=sys.stderr, flush=True)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    endpoints = parser.add_mutually_exclusive_group()
    endpoints.add_argument("--ollama-url", default="http://127.0.0.1:11434",
                        help="Ollama base URL (default: http://127.0.0.1:11434)")
    endpoints.add_argument("--api-url", help="Translation API base URL; uses its configured model")
    parser.add_argument("--model", help="Direct Ollama model (default: translategemma:4b)")
    parser.add_argument("--file", type=Path, default=ROOT / "samples" / "babicka-cs.txt",
                        help="UTF-8 Czech input file (default: bundled Babička excerpt)")
    args = parser.parse_args()
    if args.api_url and args.model:
        parser.error("--model applies only to direct Ollama; --api-url uses the server's configured model.")
    try:
        text = args.file.read_text(encoding="utf-8")
        if not text.strip() or len(text) > 10000:
            raise ValueError("The input must contain 1 to 10,000 characters of nonblank text.")
        print(f"Input: {args.file.name} ({len(text):,} characters; cs → en)", file=sys.stderr)
        started = time.monotonic()
        def progress(partial):
            if sys.stderr.isatty():
                print(f"\rGenerated {len(partial):,} characters…", end="", file=sys.stderr, flush=True)
        if args.api_url:
            result = translate_api(args.api_url, text, progress)
        else:
            model = args.model or "translategemma:4b"
            print(f"Ollama: {args.ollama_url}\nModel: {model}", file=sys.stderr, flush=True)
            translator = OllamaTranslator(model, args.ollama_url)
            print("Translating…", file=sys.stderr, flush=True)
            result = translator.translate(text, "cs", "en", progress)
        if sys.stderr.isatty():
            print(file=sys.stderr, flush=True)
        # Uncomment to inspect the translation when comparing output quality.
        # print(result["translatedText"], flush=True)
        print(f"\nCompleted in {time.monotonic() - started:.1f} s.", file=sys.stderr, flush=True)
    except (OSError, ValueError, RuntimeError) as error:
        print(f"Translation failed: {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("\nTranslation cancelled.", file=sys.stderr)
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
