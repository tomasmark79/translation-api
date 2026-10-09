# HTTP API

- `GET /health`: returns `status`, `backend`, `model` and `device`.
- `POST /translate`: accepts `{"q":"Hello","source":"en","target":"cs"}`;
  returns HTTP 202 with `jobId` and `status: pending`.
- `GET /translations/<jobId>`: returns `pending` with `partialText`, `done` with
  `translatedText` and `detectedLanguage`, or `failed` with `error`.

`source` defaults to `auto`, `target` to `cs`. Supported language codes are listed
in `LANGUAGES` in [`server.py`](../server.py). Text is limited to 10,000 characters. One worker
processes up to eight queued/running jobs in order. Results expire after ten
minutes when another job is submitted, and retained jobs are capped at 128.

Invisible editor placeholders U+FEFF and U+200B are removed from otherwise blank
lines before language detection and translation. Spaces and line breaks are
preserved by this normalization; characters within nonempty text and language
joiners such as U+200C are kept. Input containing only whitespace and these
placeholders is rejected. The 10,000-character limit applies before normalization.

The listener defaults to loopback; `--host` (or the service's `host` option)
changes the listening address. Web page origins are rejected. Chrome extensions
(`chrome-extension://<extension-id>`) call it from their service workers;
Firefox extensions (`moz-extension://<uuid>`) call it from background scripts.
Native local clients can call it without an
Origin header. It has no remote-access authentication. Request text and
translations are not written to HTTP logs.


[Back to the quick start](../README.md).
