# HTTP API

- `GET /health`: returns `status`, `backend`, `model` and `device`.
- `POST /translate`: accepts `{"q":"Hello","source":"auto","target":"cs"}`;
  returns HTTP 202 with `jobId` and `status: pending`.
- `GET /translations/<jobId>`: returns `pending` with `partialText`, `done` with
  `translatedText` and `detectedLanguage`, or `failed` with `error`.

`source` defaults to `auto`, `target` to `cs`. Supported language codes are listed
in `LANGUAGES` in [`server.py`](../server.py). Text is limited to 10,000 characters. One worker
processes up to eight queued/running jobs in order. Completed and failed results
expire ten minutes after completion when another job is submitted, and retained
jobs are capped at 128. Queued and running jobs do not expire.

Ollama connections allow up to ten minutes for a blocking network operation,
including waiting for the next stream data. This is not a total translation limit:
long texts are translated in chunks and can take several minutes. Clients should
allow at least fifteen minutes for a job, including time spent in the queue.

Invisible editor placeholders U+FEFF and U+200B are removed from otherwise blank
lines before language detection and translation. Spaces and line breaks are
preserved by this normalization; characters within nonempty text and language
joiners such as U+200C are kept. Input containing only whitespace and these
placeholders is rejected. The 10,000-character limit applies before normalization.

## Choosing the target language

Every client can choose the target independently in each `POST /translate` request.
Use `source: "auto"`, or omit `source`, for automatic source detection. `target`
accepts language codes such as `cs` (Czech), `en` (English), `de` (German), `fr`
(French), `es` (Spanish) and `pl` (Polish). Omitting `target` keeps the default `cs`;
`target: "auto"` is invalid. Explicit source codes remain available to existing
clients.

For example, an external program can request German output with automatic detection:

```sh
curl -H 'Content-Type: application/json' \
  -d '{"q":"Good morning!","source":"auto","target":"de"}' \
  http://127.0.0.1:5001/translate
```

Poll `GET /translations/<jobId>` using the returned `jobId` until `status` is
`done` or `failed`. The target belongs to that job; it is not a server-wide setting.
Ollama prompts use human-readable names for all supported language codes.

The listener defaults to loopback; `--host` (or the service's `host` option)
changes the listening address. Web page origins are rejected. Chrome extensions
(`chrome-extension://<extension-id>`) call it from their service workers;
Firefox extensions (`moz-extension://<uuid>`) call it from background scripts.
Native local clients can call it without an
Origin header. It has no remote-access authentication. Request text and
translations are not written to HTTP logs.


[Back to the quick start](../README.md).
